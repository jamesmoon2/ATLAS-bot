"""Tests for dispatcher state persistence (load_state / save_state)."""

import json

import cron.dispatcher as dispatcher


class TestLoadState:
    """load_state() reads and parses the JSON state file."""

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dispatcher, "STATE_FILE", tmp_path / "missing.json")
        assert dispatcher.load_state() == {}

    def test_corrupt_json_returns_empty(self, tmp_path, monkeypatch):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        monkeypatch.setattr(dispatcher, "STATE_FILE", bad)
        assert dispatcher.load_state() == {}

    def test_valid_state_loaded(self, tmp_path, monkeypatch):
        f = tmp_path / "state.json"
        data = {"job1": {"last_run": "2025-01-01T00:00:00", "failures": 0}}
        f.write_text(json.dumps(data))
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        assert dispatcher.load_state() == data


class TestSaveState:
    """save_state() writes JSON and creates parent directories."""

    def test_creates_parent_dirs(self, tmp_path, monkeypatch):
        f = tmp_path / "nested" / "deep" / "state.json"
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        dispatcher.save_state({"x": 1})
        assert f.exists()
        assert json.loads(f.read_text()) == {"x": 1}

    def test_round_trip_fidelity(self, tmp_path, monkeypatch):
        f = tmp_path / "state.json"
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        data = {
            "job_a": {"last_run": "2025-06-11T05:30:00-07:00", "failures": 2},
            "job_b": {"last_run": None, "failures": 0},
        }
        dispatcher.save_state(data)
        loaded = dispatcher.load_state()
        assert loaded == data

    def test_overwrites_existing_file(self, tmp_path, monkeypatch):
        f = tmp_path / "state.json"
        f.write_text('{"old": true}')
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        dispatcher.save_state({"new": True})
        assert json.loads(f.read_text()) == {"new": True}


class TestStateMigration:
    """Old string-format state entries are handled gracefully."""

    def test_old_string_format_readable(self, tmp_path, monkeypatch):
        """load_state returns old format as-is; migration happens in main()."""
        f = tmp_path / "state.json"
        f.write_text(json.dumps({"job1": "2025-01-01T00:00:00"}))
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        state = dispatcher.load_state()
        assert state["job1"] == "2025-01-01T00:00:00"

    def test_empty_state_file(self, tmp_path, monkeypatch):
        f = tmp_path / "state.json"
        f.write_text("{}")
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        assert dispatcher.load_state() == {}

    def test_save_preserves_none_values(self, tmp_path, monkeypatch):
        f = tmp_path / "state.json"
        monkeypatch.setattr(dispatcher, "STATE_FILE", f)
        data = {"job1": {"last_run": None, "failures": 0}}
        dispatcher.save_state(data)
        loaded = json.loads(f.read_text())
        assert loaded["job1"]["last_run"] is None
