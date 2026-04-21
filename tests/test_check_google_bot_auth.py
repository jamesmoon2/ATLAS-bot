from __future__ import annotations

from pathlib import Path

import check_google_bot_auth


def test_clean_optional_text_trims_blank_values():
    assert check_google_bot_auth._clean_optional_text("  hello  ") == "hello"
    assert check_google_bot_auth._clean_optional_text("   ") is None


def test_connector_status_matches_email_case_insensitively():
    status = check_google_bot_auth.ConnectorStatus.from_values(
        status="connected",
        email="ClaudiaMooney00@gmail.com",
    )

    assert status.matches_email("claudiamooney00@gmail.com")


def test_build_text_report_includes_setup_guidance_for_mismatch():
    result = check_google_bot_auth.ProbeResult(
        google_calendar=check_google_bot_auth.ConnectorStatus.from_values(
            status="connected",
            email="jamesmoon2@gmail.com",
            display_name="James Calendar",
            message="connected",
        ),
        gmail=check_google_bot_auth.ConnectorStatus.from_values(
            status="connected",
            email="jamesmoon2@gmail.com",
            display_name="James Mail",
            message="connected",
        ),
    )

    report = check_google_bot_auth.build_text_report(
        result,
        expected_email="claudiamooney00@gmail.com",
        metadata={
            "client_secret_file": Path("/tmp/client.json"),
            "token_file": Path("/tmp/token.json"),
        },
    )

    assert "Result: needs setup" in report
    assert "oauth_setup.py" in report
    assert "claudiamooney00@gmail.com" in report


def test_run_probe_returns_unauthenticated_when_setup_missing(monkeypatch):
    class MissingAuthError(Exception):
        pass

    monkeypatch.setattr(
        check_google_bot_auth,
        "_load_google_bot_modules",
        lambda: (
            None,
            None,
            lambda: (_ for _ in ()).throw(MissingAuthError("missing token")),
            {
                "client_secret_file": Path("/tmp/client.json"),
                "token_file": Path("/tmp/token.json"),
                "auth_missing_error": MissingAuthError,
            },
        ),
    )

    result, metadata = check_google_bot_auth.run_probe()

    assert metadata["token_file"] == Path("/tmp/token.json")
    assert result.gmail.status == "unauthenticated"
    assert result.google_calendar.status == "unauthenticated"


def test_main_returns_success_for_matching_connected_account(monkeypatch, capsys):
    monkeypatch.setattr(
        check_google_bot_auth,
        "run_probe",
        lambda: (
            check_google_bot_auth.ProbeResult(
                google_calendar=check_google_bot_auth.ConnectorStatus.from_values(
                    status="connected",
                    email="claudiamooney00@gmail.com",
                    display_name="Claudia Calendar",
                    message="connected",
                ),
                gmail=check_google_bot_auth.ConnectorStatus.from_values(
                    status="connected",
                    email="claudiamooney00@gmail.com",
                    display_name="Claudia Mail",
                    message="connected",
                ),
            ),
            {
                "client_secret_file": Path("/tmp/client.json"),
                "token_file": Path("/tmp/token.json"),
                "auth_missing_error": RuntimeError,
            },
        ),
    )

    exit_code = check_google_bot_auth.main(["--expected-email", "claudiamooney00@gmail.com"])

    assert exit_code == 0
    assert "Result: ready" in capsys.readouterr().out
