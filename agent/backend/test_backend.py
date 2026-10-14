import json

import backend


def test_extract_event_json_handles_wrapped_json(monkeypatch):
    monkeypatch.setattr(backend, "call_llama3", lambda prompt: "Sure!\n{\"title\":\"Dinner with Sara\", \"datetime_text\":\"tomorrow at 8 pm\", \"duration_minutes\": 90}\nThanks!")

    result = backend.extract_event_json("Schedule dinner with Sara tomorrow at 8 pm for 1.5 hours")

    assert result == {
        "title": "Dinner with Sara",
        "datetime_text": "tomorrow at 8 pm",
        "duration_minutes": 90,
    }


def test_format_event_time_handles_date_only_events():
    assert backend.format_event_time("2026-10-14") == "14 October 2026 at 00:00"
