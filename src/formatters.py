"""Report formatters — Claude AI and plain-text fallback."""

import json
import logging
from datetime import date

log = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "You are a school assistant summarizing daily Librus data for a parent.\n"
    "Write a clear, friendly Telegram message in Polish.\n"
    "Use Telegram Markdown: *bold*, _italic_, bullet points with •\n"
    "Be concise. Highlight what's urgent (homework due soon, low grades, new announcements).\n"
    "Structure: greeting with child name, today's lessons, upcoming homework, recent grades, announcements, attendance.\n"
    "End with a friendly note."
)


def generate_report_with_claude(data: dict, account_cfg: dict, global_cfg: dict) -> str | None:
    """Use Claude API to generate a formatted Telegram report. Returns None on failure."""
    import urllib.request

    api_key = global_cfg.get("claude", {}).get("api_key", "")
    if not api_key:
        log.warning("No Claude API key — falling back to built-in formatter")
        return None

    model = global_cfg.get("claude", {}).get("model", "claude-haiku-4-5-20251001")
    max_tokens = global_cfg.get("claude", {}).get("max_tokens", 1500)

    prompt_template = account_cfg.get("report_prompt") or global_cfg.get("report_prompt", "") or DEFAULT_PROMPT
    user_msg = f"Child: {data['account_name']}\nDate: {data['date']}\n\nData:\n{json.dumps(data, ensure_ascii=False, indent=2)}"

    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": prompt_template,
        "messages": [{"role": "user", "content": user_msg}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text = "".join(b.get("text", "") for b in result.get("content", []))
            log.info(f"[{data['account_name']}]  Claude generated report ({len(text)} chars)")
            return text
    except Exception as e:
        log.warning(f"[{data['account_name']}]  Claude API failed: {e} — using fallback formatter")
        return None


def format_report_fallback(data: dict) -> str:
    """Simple built-in formatter when no Claude API key is set."""
    today = date.fromisoformat(data["date"])
    lines = [
        f"📚 *Librus — {data['account_name']}*",
        f"📅 {today.strftime('%A, %d.%m.%Y')}",
        "",
    ]

    # Today's lessons
    if data.get("today_lessons"):
        lines.append("🕐 *Plan lekcji na dziś:*")
        for l in data["today_lessons"]:
            hour = f" ({l['hour']})" if l.get("hour") else ""
            room = f" [sala {l['room']}]" if l.get("room") else ""
            lines.append(f"  {l['period']}. {l['subject']}{hour}{room}")
    else:
        lines.append("🕐 *Plan lekcji na dziś:* brak / wolny dzień")
    lines.append("")

    # Tomorrow's lessons
    if data.get("tomorrow_lessons"):
        tomorrow_date = data.get("tomorrow_date", "")
        try:
            tomorrow_fmt = date.fromisoformat(tomorrow_date).strftime("%A, %d.%m")
        except Exception:
            tomorrow_fmt = tomorrow_date
        lines.append(f"📅 *Plan lekcji na jutro ({tomorrow_fmt}):*")
        for l in data["tomorrow_lessons"]:
            hour = f" ({l['hour']})" if l.get("hour") else ""
            room = f" [sala {l['room']}]" if l.get("room") else ""
            lines.append(f"  {l['period']}. {l['subject']}{hour}{room}")
    else:
        lines.append("📅 *Plan lekcji na jutro:* brak / wolny dzień")
    lines.append("")

    # Homework
    if data.get("homework"):
        lines.append("📝 *Zadania domowe (7 dni):*")
        for h in data["homework"]:
            lines.append(f"  • *{h['subject']}* — do {h['due']}")
            if h.get("description"):
                lines.append(f"    _{h['description'][:120]}_")
    else:
        lines.append("📝 *Zadania domowe:* brak ✅")
    lines.append("")

    # Schedule (Terminarz)
    if data.get("schedule_events"):
        lines.append("🗓️ *Terminarz (dziś – koniec tygodnia):*")
        current_date = None
        for ev in data["schedule_events"]:
            ev_date = ev["date"]
            if ev_date != current_date:
                current_date = ev_date
                try:
                    fmt = date.fromisoformat(ev_date).strftime("%A, %d.%m")
                except Exception:
                    fmt = ev_date
                lines.append(f"  *{fmt}:*")
            number_str = f" [l.{ev['number']}]" if ev.get("number") and str(ev["number"]) not in ("unknown", "0") else ""
            lines.append(f"    • *{ev['subject']}*{number_str}: {ev['title']}")
    else:
        lines.append("🗓️ *Terminarz:* brak wydarzeń w tym tygodniu")
    lines.append("")

    # Grades
    if data.get("grades"):
        lines.append("🏆 *Ostatnie oceny:*")
        for g in data["grades"][:8]:
            lines.append(f"  • {g['subject']}: *{g['grade']}* (waga: {g['weight']}) — {g['category']}")
    else:
        lines.append("🏆 *Oceny:* brak nowych")
    lines.append("")

    # Announcements
    if data.get("announcements"):
        lines.append("📢 *Ogłoszenia:*")
        for a in data["announcements"][:4]:
            lines.append(f"  • *{a['title']}*")
            if a.get("description"):
                desc = a['description'][:300] + ("..." if len(a['description']) > 300 else "")
                lines.append(f"    _{desc}_")
            lines.append("")
    else:
        lines.append("📢 *Ogłoszenia:* brak")
    lines.append("")

    # Messages
    if data.get("messages"):
        lines.append("✉️ *Wiadomości (dziś):*")
        for m in data["messages"]:
            unread_mark = " 🔴" if m.get("unread") else ""
            lines.append(f"  • *{m['author']}*: {m['title']}{unread_mark}")
            if m.get("body"):
                body = m['body'][:300] + ("..." if len(m['body']) > 300 else "")
                lines.append(f"    _{body}_")
            lines.append("")
    else:
        lines.append("✉️ *Wiadomości:* brak nowych")
    lines.append("")

    # Attendance
    att = data.get("attendance", {})
    if att:
        lines.append(f"📊 *Frekwencja:* S1: {att.get('semester1','—')} | S2: {att.get('semester2','—')} | Łącznie: {att.get('overall','—')}")

    lines.append("")
    lines.append("_🤖 Librus Bot_")
    return "\n".join(lines)
