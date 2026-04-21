from __future__ import annotations

from src.google_bot_mcp.tools import _decode_body_data, _event_summary, _extract_text_bodies


def test_decode_body_data_handles_base64url():
    assert _decode_body_data("SGVsbG8=") == "Hello"


def test_extract_text_bodies_prefers_nested_plain_and_html_parts():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": "SGVsbG8gV29ybGQ="}},
            {"mimeType": "text/html", "body": {"data": "PHA-SGVsbG88L3A-"}},
        ],
    }

    plain_text, html_text = _extract_text_bodies(payload)

    assert plain_text == "Hello World"
    assert html_text == "<p>Hello</p>"


def test_event_summary_handles_datetime_and_attendees():
    event = {
        "id": "evt_123",
        "status": "confirmed",
        "summary": "Dinner",
        "organizer": {"email": "claudiamooney00@gmail.com"},
        "start": {"dateTime": "2026-04-20T18:00:00-07:00"},
        "end": {"dateTime": "2026-04-20T19:00:00-07:00"},
        "attendees": [{"email": "a@example.com", "responseStatus": "accepted"}],
    }

    summary = _event_summary(event)

    assert summary["calendar_id"] == "claudiamooney00@gmail.com"
    assert summary["start"] == "2026-04-20T18:00:00-07:00"
    assert summary["attendees"][0]["email"] == "a@example.com"
