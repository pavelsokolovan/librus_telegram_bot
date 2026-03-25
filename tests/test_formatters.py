"""Tests for src.formatters — Claude API mocked, fallback is pure logic."""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.formatters import format_report_fallback, generate_report_with_claude


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _base_data(**overrides):
    data = {
        "account_name": "Jan",
        "date": "2026-03-25",
        "today_lessons": [],
        "tomorrow_lessons": [],
        "tomorrow_date": "2026-03-26",
        "homework": [],
        "schedule_events": [],
        "grades": [],
        "grades_note": "",
        "averages": {},
        "announcements": [],
        "messages": [],
        "attendance": {},
    }
    data.update(overrides)
    return data


# ── format_report_fallback ────────────────────────────────────────────────────

class TestFallbackFormatter:
    def test_header_contains_name_and_date(self):
        report = format_report_fallback(_base_data())
        assert "Jan" in report
        assert "25.03.2026" in report

    def test_empty_data_shows_defaults(self):
        report = format_report_fallback(_base_data())
        assert "brak / wolny dzień" in report
        assert "brak ✅" in report
        assert "brak wydarzeń" in report
        assert "brak nowych" in report
        assert "Librus Bot" in report

    def test_today_lessons_rendered(self):
        data = _base_data(today_lessons=[
            {"period": "1", "subject": "Matematyka", "hour": "08:00–08:45", "room": ""},
            {"period": "2", "subject": "Fizyka", "hour": "08:55–09:40", "room": "201"},
        ])
        report = format_report_fallback(data)
        assert "Matematyka" in report
        assert "Fizyka" in report
        assert "08:00–08:45" in report
        assert "sala 201" in report

    def test_tomorrow_lessons_rendered(self):
        data = _base_data(
            tomorrow_lessons=[{"period": "3", "subject": "Chemia", "hour": "10:00–10:45", "room": ""}],
            tomorrow_date="2026-03-26",
        )
        report = format_report_fallback(data)
        assert "Chemia" in report
        assert "jutro" in report

    def test_homework_rendered(self):
        data = _base_data(homework=[
            {"subject": "Polski", "due": "2026-03-27", "description": "Napisz esej", "teacher": "T"},
        ])
        report = format_report_fallback(data)
        assert "Polski" in report
        assert "2026-03-27" in report
        assert "Napisz esej" in report

    def test_schedule_events_grouped_by_day(self):
        data = _base_data(schedule_events=[
            {"date": "2026-03-25", "subject": "Matematyka", "title": "Kartkówka", "number": "3"},
            {"date": "2026-03-25", "subject": "Fizyka", "title": "Sprawdzian", "number": "5"},
            {"date": "2026-03-26", "subject": "Historia", "title": "Odpowiedź", "number": "2"},
        ])
        report = format_report_fallback(data)
        assert "Kartkówka" in report
        assert "Sprawdzian" in report
        assert "Odpowiedź" in report
        # Lesson numbers shown
        assert "[l.3]" in report
        assert "[l.5]" in report

    def test_schedule_events_unknown_number_hidden(self):
        data = _base_data(schedule_events=[
            {"date": "2026-03-25", "subject": "X", "title": "Y", "number": "unknown"},
        ])
        report = format_report_fallback(data)
        assert "[l." not in report

    def test_grades_rendered(self):
        data = _base_data(grades=[
            {"subject": "Matematyka", "grade": "5", "weight": "3", "category": "Kartkówka"},
        ])
        report = format_report_fallback(data)
        assert "Matematyka" in report
        assert "*5*" in report
        assert "waga: 3" in report

    def test_grades_limited_to_8(self):
        data = _base_data(grades=[
            {"subject": f"Subj{i}", "grade": "4", "weight": "1", "category": "Test"}
            for i in range(12)
        ])
        report = format_report_fallback(data)
        assert "Subj7" in report   # 8th (0-indexed: 7)
        assert "Subj8" not in report  # 9th should be omitted

    def test_announcements_rendered(self):
        data = _base_data(announcements=[
            {"title": "Ważne ogłoszenie", "description": "Szczegóły tutaj"},
        ])
        report = format_report_fallback(data)
        assert "Ważne ogłoszenie" in report
        assert "Szczegóły tutaj" in report

    def test_announcements_limited_to_4(self):
        data = _base_data(announcements=[
            {"title": f"Ann{i}", "description": ""} for i in range(6)
        ])
        report = format_report_fallback(data)
        assert "Ann3" in report
        assert "Ann4" not in report

    def test_messages_rendered_with_unread_mark(self):
        data = _base_data(messages=[
            {"author": "Nauczyciel", "title": "Uwaga", "unread": True, "body": "Treść wiadomości"},
            {"author": "Dyrektor", "title": "Info", "unread": False, "body": ""},
        ])
        report = format_report_fallback(data)
        assert "Nauczyciel" in report
        assert "🔴" in report
        assert "Treść wiadomości" in report
        assert "Info" in report

    def test_attendance_rendered(self):
        data = _base_data(attendance={
            "semester1": "95.0%", "semester2": "87.0%", "overall": "91.0%",
        })
        report = format_report_fallback(data)
        assert "95.0%" in report
        assert "91.0%" in report

    def test_long_message_body_truncated(self):
        data = _base_data(messages=[
            {"author": "T", "title": "T", "unread": False, "body": "B" * 400},
        ])
        report = format_report_fallback(data)
        assert "..." in report

    def test_long_announcement_desc_truncated(self):
        data = _base_data(announcements=[
            {"title": "T", "description": "D" * 400},
        ])
        report = format_report_fallback(data)
        assert "..." in report


# ── generate_report_with_claude ───────────────────────────────────────────────

class TestClaudeReport:
    def test_returns_none_when_no_api_key(self):
        result = generate_report_with_claude(
            _base_data(), {}, {"claude": {}}
        )
        assert result is None

    def test_returns_none_when_empty_api_key(self):
        result = generate_report_with_claude(
            _base_data(), {}, {"claude": {"api_key": ""}}
        )
        assert result is None

    @patch("urllib.request.urlopen")
    def test_calls_api_and_returns_text(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({
            "content": [{"text": "Cześć! Raport dla Jan..."}]
        }).encode("utf-8")
        mock_urlopen.return_value = mock_resp

        cfg = {"claude": {"api_key": "sk-test", "model": "test-model", "max_tokens": 500}}
        result = generate_report_with_claude(_base_data(), {}, cfg)

        assert result == "Cześć! Raport dla Jan..."
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen", side_effect=Exception("API error"))
    def test_returns_none_on_api_failure(self, _):
        cfg = {"claude": {"api_key": "sk-test"}}
        result = generate_report_with_claude(_base_data(), {}, cfg)
        assert result is None

    @patch("urllib.request.urlopen")
    def test_uses_account_prompt_override(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"content": [{"text": "OK"}]}).encode("utf-8")
        mock_urlopen.return_value = mock_resp

        cfg = {"claude": {"api_key": "sk-test"}, "report_prompt": "global prompt"}
        account = {"report_prompt": "account-level prompt"}
        generate_report_with_claude(_base_data(), account, cfg)

        # Verify request body contains account-level prompt
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        assert body["system"] == "account-level prompt"

    @patch("urllib.request.urlopen")
    def test_falls_back_to_global_prompt(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"content": [{"text": "OK"}]}).encode("utf-8")
        mock_urlopen.return_value = mock_resp

        cfg = {"claude": {"api_key": "sk-test"}, "report_prompt": "global prompt"}
        generate_report_with_claude(_base_data(), {}, cfg)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode("utf-8"))
        assert body["system"] == "global prompt"
