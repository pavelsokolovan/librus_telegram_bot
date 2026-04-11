"""Data fetchers — each function fetches one category from Librus and returns a dict fragment."""

import logging
import traceback
from collections import defaultdict
from datetime import date, timedelta

log = logging.getLogger(__name__)


def _safe_attr(obj, name, default=""):
    return str(getattr(obj, name, default))


# ── Messages ───────────────────────────────────────────────────────────────────

def fetch_messages(client, name: str, today: date) -> dict:
    from librus_apix.messages import get_received, message_content

    try:
        msgs = get_received(client, page=0)
        today_msgs = [m for m in msgs if _safe_attr(m, "date").startswith(str(today))]
        messages_with_body = []
        for m in today_msgs:
            try:
                detail = message_content(client, m.href)
                raw_body = _safe_attr(detail, "content").strip()
                body = raw_body[:600] + ("..." if len(raw_body) > 600 else "")
            except Exception as me:
                log.warning(f"[{name}]  message body fetch failed for '{m.title}': {me}")
                body = ""
            messages_with_body.append({
                "author": _safe_attr(m, "author"),
                "title": _safe_attr(m, "title"),
                "date": _safe_attr(m, "date"),
                "unread": bool(getattr(m, "unread", False)),
                "body": body,
            })
        log.info(f"[{name}]  messages today: {len(messages_with_body)} (of {len(msgs)} total on page 0)")
        return {"messages": messages_with_body}
    except Exception as e:
        log.warning(f"[{name}]  messages failed: {e}")
        return {"messages": []}


# ── Announcements ──────────────────────────────────────────────────────────────

def fetch_announcements(client, name: str, today: date) -> dict:
    from librus_apix.announcements import get_announcements

    try:
        raw = get_announcements(client)
        items = [
            {
                "title": a.title,
                "description": ((getattr(a, "description", "") or "")[:400]
                                + ("..." if len(getattr(a, "description", "") or "") > 400 else "")),
                "author": getattr(a, "author", ""),
                "date": _safe_attr(a, "date"),
            }
            for a in raw
            if _safe_attr(a, "date") == str(today)
        ]
        log.info(f"[{name}]  announcements today: {len(items)} (of {len(raw)} total)")
        return {"announcements": items}
    except Exception as e:
        log.warning(f"[{name}]  announcements failed: {e}")
        return {"announcements": []}


# ── Grades ─────────────────────────────────────────────────────────────────────

def fetch_grades(client, name: str, grades_new_days: int = 3) -> dict:
    from librus_apix.grades import get_grades

    try:
        result = get_grades(client)
        log.debug(f"[{name}]  grades raw result type: {type(result)}, len: {len(result) if result else 0}")

        # get_grades returns (sem_grades, avg_grades, descriptive_grades) — 3-tuple
        grades_semesters = result[0] if result and len(result) > 0 else []
        averages_raw = result[1] if result and len(result) > 1 else {}

        grades_list = []
        if isinstance(grades_semesters, list):
            for i, semester in enumerate(grades_semesters):
                if not isinstance(semester, dict):
                    log.warning(f"[{name}]  semester[{i}] is not a dict: {type(semester)}")
                    continue
                for subject, marks in semester.items():
                    if not isinstance(marks, list):
                        continue
                    for m in marks:
                        grades_list.append({
                            "subject": subject,
                            "grade": _safe_attr(m, "grade", "—"),
                            "weight": _safe_attr(m, "weight", "—"),
                            "category": _safe_attr(m, "category"),
                            "date": _safe_attr(m, "date"),
                            "teacher": _safe_attr(m, "teacher"),
                        })

        grades_list.sort(key=lambda x: x["date"], reverse=True)

        # averages_raw is DefaultDict[str, List[Gpa]] — pick the latest semester gpa per subject
        averages = {}
        for subject, gpa_list in (averages_raw or {}).items():
            if gpa_list:
                best = max(gpa_list, key=lambda g: g.semester)
                averages[subject] = str(best.gpa)

        cutoff = (date.today() - timedelta(days=grades_new_days)).isoformat()
        recent = [g for g in grades_list if g["date"] >= cutoff]

        data: dict = {"averages": averages}
        if recent:
            log.info(f"[{name}]  grades: {len(recent)} new in last {grades_new_days} days (of {len(grades_list)} total)")
            data["grades"] = recent
            data["grades_note"] = f"nowe oceny z ostatnich {grades_new_days} dni"
        else:
            log.info(f"[{name}]  grades: 0 new in last {grades_new_days} days")
            data["grades"] = []
            data["grades_note"] = ""
        return data

    except Exception as e:
        log.warning(f"[{name}]  grades failed: {e}\n{traceback.format_exc()}")
        return {"grades": [], "averages": {}, "grades_note": ""}


# ── Homework ───────────────────────────────────────────────────────────────────

def fetch_homework(client, name: str, today: date) -> dict:
    from librus_apix.homework import get_homework

    try:
        week_ahead = today + timedelta(days=7)
        raw = get_homework(client, str(today), str(week_ahead))
        items = [
            {
                "subject": _safe_attr(h, "lesson", "—"),
                "due": _safe_attr(h, "completion_date", "—"),
                "description": _safe_attr(h, "description")[:300],
                "teacher": _safe_attr(h, "teacher"),
            }
            for h in raw
        ]
        log.info(f"[{name}]  homework: {len(items)}")
        return {"homework": items}
    except Exception as e:
        log.warning(f"[{name}]  homework failed: {e}")
        return {"homework": []}


# ── Schedule (Terminarz) ──────────────────────────────────────────────────────

def fetch_schedule(client, name: str, today: date) -> dict:
    from librus_apix.schedule import get_schedule

    try:
        weekday = today.weekday()
        end_of_week = today + timedelta(days=11 - weekday)  # always next week's Friday

        months_to_fetch: set = set()
        cursor = today
        while cursor <= end_of_week:
            months_to_fetch.add((str(cursor.month).zfill(2), str(cursor.year)))
            cursor += timedelta(days=1)

        events = []
        for month_str, year_str in months_to_fetch:
            month_schedule = get_schedule(client, month_str, year_str)
            for day_num, day_events in month_schedule.items():
                try:
                    event_date = date(int(year_str), int(month_str), day_num)
                except ValueError:
                    continue
                if today <= event_date <= end_of_week:
                    for ev in day_events:
                        events.append({
                            "date": str(event_date),
                            "subject": str(ev.subject),
                            "title": str(ev.title),
                            "number": str(ev.number),
                            "data": ev.data,
                        })

        events.sort(key=lambda x: (x["date"], str(x["number"])))
        log.info(f"[{name}]  schedule events (today–{end_of_week}): {len(events)}")
        return {"schedule_events": events}

    except Exception as e:
        log.warning(f"[{name}]  schedule failed: {e}\n{traceback.format_exc()}")
        return {"schedule_events": []}


# ── Attendance ─────────────────────────────────────────────────────────────────

def fetch_attendance(client, name: str) -> dict:
    from librus_apix.attendance import get_attendance_frequency

    try:
        s1, s2, overall = get_attendance_frequency(client)
        att = {
            "semester1": f"{s1 * 100:.1f}%",
            "semester2": f"{s2 * 100:.1f}%",
            "overall": f"{overall * 100:.1f}%",
        }
        log.info(f"[{name}]  attendance: {att['overall']}")
        return {"attendance": att}
    except Exception as e:
        log.warning(f"[{name}]  attendance failed: {e}")
        return {"attendance": {}}


# ── Timetable ──────────────────────────────────────────────────────────────────

def fetch_timetable(client, name: str, today: date) -> dict:
    from librus_apix.timetable import get_timetable

    try:
        tomorrow = today + timedelta(days=1)
        if tomorrow.weekday() == 5:
            tomorrow += timedelta(days=2)
        elif tomorrow.weekday() == 6:
            tomorrow += timedelta(days=1)

        monday = today - timedelta(days=today.weekday())
        log.debug(f"[{name}]  fetching timetable for week starting: {monday}")
        tt = get_timetable(client, monday)

        all_periods = []
        for item in (tt if isinstance(tt, list) else []):
            if isinstance(item, list):
                all_periods.extend(item)
            else:
                all_periods.append(item)

        def extract_lessons(periods, target_date):
            result = []
            for p in periods:
                if _safe_attr(p, "date") != str(target_date):
                    continue
                subject = _safe_attr(p, "subject").strip()
                if not subject:
                    continue
                result.append({
                    "period": _safe_attr(p, "number", "?"),
                    "subject": subject,
                    "teacher": _safe_attr(p, "teacher_and_classroom"),
                    "hour": f"{getattr(p, 'date_from', '')}–{getattr(p, 'date_to', '')}",
                    "room": "",
                })
            return result

        today_lessons = extract_lessons(all_periods, today)
        tomorrow_lessons = extract_lessons(all_periods, tomorrow)
        log.info(f"[{name}]  today's lessons: {len(today_lessons)}, tomorrow's: {len(tomorrow_lessons)}")

        # If tomorrow is next week Monday and not found, fetch that week
        if not tomorrow_lessons and tomorrow.weekday() == 0:
            log.debug(f"[{name}]  fetching next week timetable for: {tomorrow}")
            tt2 = get_timetable(client, tomorrow)
            periods2 = []
            for item in (tt2 if isinstance(tt2, list) else []):
                if isinstance(item, list):
                    periods2.extend(item)
                else:
                    periods2.append(item)
            tomorrow_lessons = extract_lessons(periods2, tomorrow)
            log.info(f"[{name}]  tomorrow's lessons (next week fetch): {len(tomorrow_lessons)}")

        return {
            "today_lessons": today_lessons,
            "tomorrow_lessons": tomorrow_lessons,
            "tomorrow_date": str(tomorrow),
        }

    except Exception as e:
        log.warning(f"[{name}]  timetable failed: {e}\n{traceback.format_exc()}")
        return {
            "today_lessons": [],
            "tomorrow_lessons": [],
            "tomorrow_date": str(today + timedelta(days=1)),
        }


# ── Aggregate ──────────────────────────────────────────────────────────────────

def fetch_all(account_cfg: dict) -> dict:
    """Fetch all data categories for one Librus account and return a combined dict."""
    from librus_apix.client import new_client

    name = account_cfg["name"]
    log.info(f"[{name}] Connecting to Librus...")

    client = new_client()
    client.get_token(account_cfg["username"], account_cfg["password"])
    log.info(f"[{name}] Logged in OK")

    today = date.today()
    data: dict = {"account_name": name, "date": str(today)}

    data.update(fetch_messages(client, name, today))
    data.update(fetch_announcements(client, name, today))
    data.update(fetch_grades(client, name, account_cfg.get("grades_new_days", 3)))
    data.update(fetch_homework(client, name, today))
    data.update(fetch_schedule(client, name, today))
    data.update(fetch_attendance(client, name))
    data.update(fetch_timetable(client, name, today))

    return data
