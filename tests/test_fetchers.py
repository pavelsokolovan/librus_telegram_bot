"""Tests for src.fetchers — all Librus API calls are mocked."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.fetchers import (
    _safe_attr,
    fetch_messages,
    fetch_announcements,
    fetch_grades,
    fetch_homework,
    fetch_schedule,
    fetch_attendance,
    fetch_timetable,
    fetch_all,
)

CLIENT = MagicMock()
NAME = "TestKid"


# ── _safe_attr ─────────────────────────────────────────────────────────────────

class TestSafeAttr:
    def test_returns_string_value(self):
        obj = SimpleNamespace(foo="bar")
        assert _safe_attr(obj, "foo") == "bar"

    def test_returns_default_when_missing(self):
        assert _safe_attr(SimpleNamespace(), "missing", "DEF") == "DEF"

    def test_converts_to_string(self):
        obj = SimpleNamespace(num=42)
        assert _safe_attr(obj, "num") == "42"


# ── fetch_messages ─────────────────────────────────────────────────────────────

class TestFetchMessages:
    def _msg(self, title, msg_date, author="Teacher", unread=False):
        return SimpleNamespace(
            title=title, date=msg_date, author=author,
            unread=unread, href="/msg/1",
        )

    @patch("src.fetchers.message_content", create=True)
    @patch("src.fetchers.get_received", create=True)
    def test_filters_today_only(self, mock_recv, mock_content):
        today = date(2026, 3, 25)
        mock_recv.return_value = [
            self._msg("Today", "2026-03-25 08:00"),
            self._msg("Yesterday", "2026-03-24 09:00"),
        ]
        mock_content.return_value = SimpleNamespace(content="Body text")

        with patch("librus_apix.messages.get_received", mock_recv), \
             patch("librus_apix.messages.message_content", mock_content):
            result = fetch_messages(CLIENT, NAME, today)

        assert len(result["messages"]) == 1
        assert result["messages"][0]["title"] == "Today"
        assert result["messages"][0]["body"] == "Body text"

    @patch("src.fetchers.message_content", create=True)
    @patch("src.fetchers.get_received", create=True)
    def test_truncates_long_body(self, mock_recv, mock_content):
        today = date(2026, 3, 25)
        mock_recv.return_value = [self._msg("Msg", "2026-03-25 10:00")]
        mock_content.return_value = SimpleNamespace(content="A" * 700)

        with patch("librus_apix.messages.get_received", mock_recv), \
             patch("librus_apix.messages.message_content", mock_content):
            result = fetch_messages(CLIENT, NAME, today)

        assert result["messages"][0]["body"].endswith("...")
        assert len(result["messages"][0]["body"]) == 603  # 600 + "..."

    @patch("librus_apix.messages.get_received", side_effect=Exception("net error"))
    def test_returns_empty_on_error(self, _):
        result = fetch_messages(CLIENT, NAME, date(2026, 3, 25))
        assert result == {"messages": []}

    @patch("src.fetchers.message_content", create=True)
    @patch("src.fetchers.get_received", create=True)
    def test_body_fetch_failure_yields_empty_body(self, mock_recv, mock_content):
        today = date(2026, 3, 25)
        mock_recv.return_value = [self._msg("Msg", "2026-03-25 10:00")]
        mock_content.side_effect = Exception("detail fail")

        with patch("librus_apix.messages.get_received", mock_recv), \
             patch("librus_apix.messages.message_content", mock_content):
            result = fetch_messages(CLIENT, NAME, today)

        assert result["messages"][0]["body"] == ""


# ── fetch_announcements ───────────────────────────────────────────────────────

class TestFetchAnnouncements:
    def _ann(self, title, ann_date, desc="Some desc", author="Admin"):
        return SimpleNamespace(title=title, date=ann_date, description=desc, author=author)

    @patch("librus_apix.announcements.get_announcements")
    def test_filters_today_only(self, mock_get):
        today = date(2026, 3, 25)
        mock_get.return_value = [
            self._ann("Today Ann", "2026-03-25"),
            self._ann("Old Ann", "2026-03-20"),
        ]
        result = fetch_announcements(CLIENT, NAME, today)
        assert len(result["announcements"]) == 1
        assert result["announcements"][0]["title"] == "Today Ann"

    @patch("librus_apix.announcements.get_announcements")
    def test_truncates_long_description(self, mock_get):
        today = date(2026, 3, 25)
        mock_get.return_value = [self._ann("X", "2026-03-25", desc="D" * 500)]
        result = fetch_announcements(CLIENT, NAME, today)
        assert result["announcements"][0]["description"].endswith("...")

    @patch("librus_apix.announcements.get_announcements", side_effect=Exception("fail"))
    def test_returns_empty_on_error(self, _):
        result = fetch_announcements(CLIENT, NAME, date(2026, 3, 25))
        assert result == {"announcements": []}


# ── fetch_grades ──────────────────────────────────────────────────────────────

class TestFetchGrades:
    def _grade(self, subject, grade_val, grade_date, weight="3", category="Kartkówka", teacher="T"):
        return SimpleNamespace(grade=grade_val, date=grade_date, weight=weight, category=category, teacher=teacher)

    @patch("librus_apix.grades.get_grades")
    def test_returns_recent_grades(self, mock_get):
        today = date(2026, 3, 25)
        mock_get.return_value = (
            [{"Matematyka": [self._grade("Matematyka", "5", "2026-03-25")]}],
            {"Matematyka": [SimpleNamespace(semester=1, gpa=4.5)]},
        )
        with patch("src.fetchers.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = date
            result = fetch_grades(CLIENT, NAME, grades_new_days=3)

        assert len(result["grades"]) == 1
        assert result["grades"][0]["grade"] == "5"
        assert result["averages"]["Matematyka"] == "4.5"
        assert "nowe oceny" in result["grades_note"]

    @patch("librus_apix.grades.get_grades")
    def test_no_recent_grades(self, mock_get):
        mock_get.return_value = (
            [{"Matematyka": [self._grade("Matematyka", "3", "2020-01-01")]}],
            {},
        )
        result = fetch_grades(CLIENT, NAME, grades_new_days=1)
        assert result["grades"] == []
        assert result["grades_note"] == ""

    @patch("librus_apix.grades.get_grades")
    def test_handles_non_dict_semester(self, mock_get):
        mock_get.return_value = (["not_a_dict"], {})
        result = fetch_grades(CLIENT, NAME)
        assert result["grades"] == []

    @patch("librus_apix.grades.get_grades", side_effect=Exception("crash"))
    def test_returns_empty_on_error(self, _):
        result = fetch_grades(CLIENT, NAME)
        assert result == {"grades": [], "averages": {}, "grades_note": ""}


# ── fetch_homework ────────────────────────────────────────────────────────────

class TestFetchHomework:
    def _hw(self, lesson, due, desc="Do exercises", teacher="T"):
        return SimpleNamespace(lesson=lesson, completion_date=due, description=desc, teacher=teacher)

    @patch("librus_apix.homework.get_homework")
    def test_returns_homework(self, mock_get):
        today = date(2026, 3, 25)
        mock_get.return_value = [self._hw("Fizyka", "2026-03-28")]
        result = fetch_homework(CLIENT, NAME, today)
        assert len(result["homework"]) == 1
        assert result["homework"][0]["subject"] == "Fizyka"
        assert result["homework"][0]["due"] == "2026-03-28"

    @patch("librus_apix.homework.get_homework", side_effect=Exception("err"))
    def test_returns_empty_on_error(self, _):
        result = fetch_homework(CLIENT, NAME, date(2026, 3, 25))
        assert result == {"homework": []}


# ── fetch_schedule ────────────────────────────────────────────────────────────

class TestFetchSchedule:
    def _event(self, subject, title, number=1, data=None):
        return SimpleNamespace(subject=subject, title=title, number=number, data=data or {})

    @patch("librus_apix.schedule.get_schedule")
    def test_returns_events_through_next_friday(self, mock_get):
        # Wednesday March 25, 2026 — next Friday is April 3
        today = date(2026, 3, 25)
        # same dict returned for any month call; April days 25-28 > April 3 so filtered
        mock_get.return_value = {
            25: [self._event("Matematyka", "Kartkówka")],
            26: [self._event("Fizyka", "Sprawdzian")],
            27: [self._event("Historia", "Zadanie")],
            28: [self._event("Weekend", "Included")],  # Saturday in [Mar 25, Apr 3]
        }
        result = fetch_schedule(CLIENT, NAME, today)
        assert len(result["schedule_events"]) == 4
        subjects = [e["subject"] for e in result["schedule_events"]]
        assert "Weekend" in subjects

    @patch("librus_apix.schedule.get_schedule")
    def test_saturday_fetches_through_next_friday(self, mock_get):
        # Saturday March 28 — next Friday is April 3 (+6 days)
        saturday = date(2026, 3, 28)

        def side_effect(client, month, year):
            if month == "03":
                return {28: [self._event("Sat", "E0")], 29: [self._event("Sun", "E00")]}
            return {
                1: [self._event("Matematyka", "E1")],
                2: [self._event("Fizyka", "E2")],
                3: [self._event("Historia", "E3")],  # next Friday — in range
                4: [self._event("Extra", "E4")],     # Saturday after next — excluded
            }

        mock_get.side_effect = side_effect
        result = fetch_schedule(CLIENT, NAME, saturday)
        assert mock_get.called
        assert len(result["schedule_events"]) == 5  # Mar 28-29 + Apr 1-3
        subjects = [e["subject"] for e in result["schedule_events"]]
        assert "Extra" not in subjects

    @patch("librus_apix.schedule.get_schedule")
    def test_friday_fetches_through_next_friday(self, mock_get):
        # Friday March 27 — next Friday is April 3 (+7 days)
        friday = date(2026, 3, 27)

        def side_effect(client, month, year):
            if month == "03":
                return {27: [self._event("Chemia", "Test")]}
            return {
                1: [self._event("Mat", "E1")],
                3: [self._event("Fiz", "E2")],  # next Friday — in range
                4: [self._event("Sat", "E3")],  # excluded
            }

        mock_get.side_effect = side_effect
        result = fetch_schedule(CLIENT, NAME, friday)
        assert len(result["schedule_events"]) == 3
        subjects = [e["subject"] for e in result["schedule_events"]]
        assert "Sat" not in subjects

    @patch("librus_apix.schedule.get_schedule")
    def test_month_boundary_spanning(self, mock_get):
        # March 30 is Monday — next Friday is April 10 (+11 days)
        monday = date(2026, 3, 30)
        march_data = {30: [self._event("Mon", "E1")], 31: [self._event("Tue", "E2")]}
        april_data = {
            1:  [self._event("Wed",  "E3")],
            2:  [self._event("Thu",  "E4")],
            3:  [self._event("Fri",  "E5")],
            6:  [self._event("Mon2", "E6")],
            7:  [self._event("Tue2", "E7")],
            8:  [self._event("Wed2", "E8")],
            9:  [self._event("Thu2", "E9")],
            10: [self._event("Fri2", "E10")],   # next Friday — in range
            11: [self._event("Sat",  "ignore")], # excluded
        }

        def side_effect(client, month, year):
            if month == "03":
                return march_data
            return april_data

        mock_get.side_effect = side_effect
        result = fetch_schedule(CLIENT, NAME, monday)
        assert len(result["schedule_events"]) == 10  # Mar30-31 + Apr1-3 + Apr6-10
        subjects = [e["subject"] for e in result["schedule_events"]]
        assert "Sat" not in subjects

    @patch("librus_apix.schedule.get_schedule", side_effect=Exception("err"))
    def test_returns_empty_on_error(self, _):
        result = fetch_schedule(CLIENT, NAME, date(2026, 3, 25))
        assert result == {"schedule_events": []}


# ── fetch_attendance ──────────────────────────────────────────────────────────

class TestFetchAttendance:
    @patch("librus_apix.attendance.get_attendance_frequency")
    def test_returns_percentages(self, mock_get):
        mock_get.return_value = (0.95, 0.87, 0.91)
        result = fetch_attendance(CLIENT, NAME)
        assert result["attendance"]["semester1"] == "95.0%"
        assert result["attendance"]["semester2"] == "87.0%"
        assert result["attendance"]["overall"] == "91.0%"

    @patch("librus_apix.attendance.get_attendance_frequency", side_effect=Exception("err"))
    def test_returns_empty_on_error(self, _):
        result = fetch_attendance(CLIENT, NAME)
        assert result == {"attendance": {}}


# ── fetch_timetable ───────────────────────────────────────────────────────────

class TestFetchTimetable:
    def _period(self, subject, period_date, number="1", teacher_and_classroom="T/101", date_from="08:00", date_to="08:45"):
        return SimpleNamespace(
            subject=subject, date=str(period_date), number=number,
            teacher_and_classroom=teacher_and_classroom,
            date_from=date_from, date_to=date_to,
        )

    @patch("librus_apix.timetable.get_timetable")
    def test_extracts_today_and_tomorrow(self, mock_get):
        today = date(2026, 3, 25)  # Wednesday
        tomorrow = date(2026, 3, 26)
        mock_get.return_value = [
            [self._period("Matematyka", today), self._period("Fizyka", today)],
            [self._period("Historia", tomorrow)],
        ]
        result = fetch_timetable(CLIENT, NAME, today)
        assert len(result["today_lessons"]) == 2
        assert len(result["tomorrow_lessons"]) == 1
        assert result["tomorrow_date"] == "2026-03-26"

    @patch("librus_apix.timetable.get_timetable")
    def test_friday_tomorrow_skips_to_monday(self, mock_get):
        friday = date(2026, 3, 27)
        monday = date(2026, 3, 30)
        # First call: this week; Second call: next week (Monday)
        mock_get.side_effect = [
            [[self._period("Polski", friday)]],
            [[self._period("Chemia", monday)]],
        ]
        result = fetch_timetable(CLIENT, NAME, friday)
        assert result["tomorrow_date"] == "2026-03-30"
        assert len(result["today_lessons"]) == 1

    @patch("librus_apix.timetable.get_timetable")
    def test_skips_empty_subjects(self, mock_get):
        today = date(2026, 3, 25)
        mock_get.return_value = [
            [self._period("Matematyka", today), self._period("", today)],
        ]
        result = fetch_timetable(CLIENT, NAME, today)
        assert len(result["today_lessons"]) == 1

    @patch("librus_apix.timetable.get_timetable", side_effect=Exception("err"))
    def test_returns_empty_on_error(self, _):
        today = date(2026, 3, 25)
        result = fetch_timetable(CLIENT, NAME, today)
        assert result["today_lessons"] == []
        assert result["tomorrow_lessons"] == []


# ── fetch_all ─────────────────────────────────────────────────────────────────

class TestFetchAll:
    @patch("src.fetchers.fetch_timetable", return_value={"today_lessons": [], "tomorrow_lessons": [], "tomorrow_date": "2026-03-26"})
    @patch("src.fetchers.fetch_attendance", return_value={"attendance": {}})
    @patch("src.fetchers.fetch_schedule", return_value={"schedule_events": []})
    @patch("src.fetchers.fetch_homework", return_value={"homework": []})
    @patch("src.fetchers.fetch_grades", return_value={"grades": [], "averages": {}, "grades_note": ""})
    @patch("src.fetchers.fetch_announcements", return_value={"announcements": []})
    @patch("src.fetchers.fetch_messages", return_value={"messages": []})
    @patch("librus_apix.client.new_client")
    def test_aggregates_all_data(self, mock_client, *mocks):
        mock_client.return_value = MagicMock()
        account_cfg = {"name": "Kid", "username": "u", "password": "p", "grades_new_days": 1}
        result = fetch_all(account_cfg)

        assert result["account_name"] == "Kid"
        assert "date" in result
        assert "messages" in result
        assert "announcements" in result
        assert "grades" in result
        assert "homework" in result
        assert "schedule_events" in result
        assert "attendance" in result
        assert "today_lessons" in result
