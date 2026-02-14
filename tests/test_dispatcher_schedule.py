"""Tests for dispatcher is_job_due() scheduling logic."""

from datetime import datetime
from zoneinfo import ZoneInfo

from cron.dispatcher import is_job_due


def _job(schedule="30 5 * * *", tz="America/Los_Angeles", job_id="test"):
    return {"id": job_id, "schedule": schedule, "timezone": tz}


class TestIsJobDue:
    """Core scheduling window checks."""

    def test_due_at_exact_scheduled_time(self):
        """Job is due when current time matches the cron schedule."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))  # 5:30 AM LA
        assert is_job_due(_job(), {}, now) is True

    def test_due_within_2min_window(self):
        """Job is due within the 2-minute execution window."""
        now = datetime(2025, 6, 11, 12, 31, 30, tzinfo=ZoneInfo("UTC"))  # 5:31:30 LA
        assert is_job_due(_job(), {}, now) is True

    def test_not_due_before_window(self):
        """Job is not due before the scheduled time."""
        now = datetime(2025, 6, 11, 12, 28, 0, tzinfo=ZoneInfo("UTC"))  # 5:28 LA
        assert is_job_due(_job(), {}, now) is False

    def test_not_due_after_window(self):
        """Job is not due after the 2-minute window."""
        now = datetime(2025, 6, 11, 12, 33, 0, tzinfo=ZoneInfo("UTC"))  # 5:33 LA
        assert is_job_due(_job(), {}, now) is False


class TestDeduplication:
    """Checks that jobs don't run twice for the same scheduled time."""

    def test_already_ran_skips(self):
        """Job is skipped if last_run >= next scheduled time."""
        now = datetime(2025, 6, 11, 12, 30, 30, tzinfo=ZoneInfo("UTC"))
        state = {
            "test": {
                "last_run": "2025-06-11T05:30:00-07:00",
                "failures": 0,
            }
        }
        assert is_job_due(_job(), state, now) is False

    def test_ran_yesterday_still_due_today(self):
        """Job ran yesterday, so it should still be due today."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        state = {
            "test": {
                "last_run": "2025-06-10T05:30:00-07:00",
                "failures": 0,
            }
        }
        assert is_job_due(_job(), state, now) is True


class TestOldStateFormat:
    """Backward compatibility with the old plain-string state format."""

    def test_old_string_state_already_ran(self):
        """Old format (plain timestamp string) is handled correctly."""
        now = datetime(2025, 6, 11, 12, 30, 30, tzinfo=ZoneInfo("UTC"))
        state = {"test": "2025-06-11T05:30:00-07:00"}
        assert is_job_due(_job(), state, now) is False

    def test_old_string_state_not_yet_ran(self):
        """Old format with yesterday's timestamp - job should be due."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        state = {"test": "2025-06-10T05:30:00-07:00"}
        assert is_job_due(_job(), state, now) is True


class TestFailureDisabling:
    """Jobs disabled after 3 consecutive failures."""

    def test_disabled_at_3_failures(self):
        """Job is not due when failure count reaches 3."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        state = {"test": {"last_run": None, "failures": 3}}
        assert is_job_due(_job(), state, now) is False

    def test_runs_with_2_failures(self):
        """Job still runs with fewer than 3 failures."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        state = {"test": {"last_run": None, "failures": 2}}
        assert is_job_due(_job(), state, now) is True


class TestTimezoneConversion:
    """Ensure cron schedules are evaluated in the job's timezone."""

    def test_utc_schedule(self):
        """UTC schedule matches UTC time directly."""
        now = datetime(2025, 6, 11, 5, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(tz="UTC"), {}, now) is True

    def test_utc_time_wrong_for_la_schedule(self):
        """5:30 UTC is not 5:30 LA, so should not be due with LA timezone."""
        now = datetime(2025, 6, 11, 5, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(tz="America/Los_Angeles"), {}, now) is False


class TestEdgeCases:
    """Edge cases: midnight, weekly, every-minute, invalid state."""

    def test_midnight_crossing(self):
        """Schedule at midnight (0 0 * * *)."""
        now = datetime(2025, 6, 12, 0, 0, 30, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(schedule="0 0 * * *", tz="UTC"), {}, now) is True

    def test_weekly_schedule(self):
        """Weekly schedule (0 9 * * 1) only runs on Monday."""
        # Wednesday at 9:00 UTC
        wed = datetime(2025, 6, 11, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(schedule="0 9 * * 1", tz="UTC"), {}, wed) is False
        # Monday at 9:00 UTC
        mon = datetime(2025, 6, 9, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(schedule="0 9 * * 1", tz="UTC"), {}, mon) is True

    def test_every_minute_schedule(self):
        """Every-minute schedule (* * * * *) is always due."""
        now = datetime(2025, 6, 11, 14, 37, 0, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(schedule="* * * * *", tz="UTC"), {}, now) is True

    def test_invalid_last_run_timestamp(self):
        """Invalid last_run value is ignored, job still runs."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        state = {"test": {"last_run": "not-a-timestamp", "failures": 0}}
        assert is_job_due(_job(), state, now) is True

    def test_empty_state(self):
        """Job with no state entry is due at scheduled time."""
        now = datetime(2025, 6, 11, 12, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert is_job_due(_job(), {}, now) is True
