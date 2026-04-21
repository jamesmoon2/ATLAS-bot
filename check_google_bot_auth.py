"""Check which Google account the repo-managed ATLAS Google bot is using."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BOT_DIR = Path(__file__).resolve().parent
GOOGLE_BOT_ROOT = BOT_DIR / "mcp-servers" / "google_bot"
VALID_STATUSES = {"connected", "unauthenticated", "unavailable", "error"}


class ProbeError(RuntimeError):
    """Raised when the repo-managed Google bot auth probe cannot complete."""


@dataclass(frozen=True)
class ConnectorStatus:
    """Normalized status for a single Google connector."""

    status: str
    email: str | None
    display_name: str | None
    message: str | None

    @classmethod
    def from_values(
        cls,
        *,
        status: str,
        email: str | None = None,
        display_name: str | None = None,
        message: str | None = None,
    ) -> ConnectorStatus:
        normalized = status.strip().lower()
        if normalized not in VALID_STATUSES:
            normalized = "error"
        return cls(
            status=normalized,
            email=_clean_optional_text(email),
            display_name=_clean_optional_text(display_name),
            message=_clean_optional_text(message),
        )

    def matches_email(self, expected_email: str | None) -> bool:
        if not expected_email:
            return True
        if self.status != "connected":
            return False
        return (self.email or "").casefold() == expected_email.casefold()

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProbeResult:
    """Normalized result for the Google bot auth probe."""

    google_calendar: ConnectorStatus
    gmail: ConnectorStatus

    def all_connected(self) -> bool:
        return self.google_calendar.status == "connected" and self.gmail.status == "connected"

    def matches_email(self, expected_email: str | None) -> bool:
        return self.google_calendar.matches_email(expected_email) and self.gmail.matches_email(
            expected_email
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "google_calendar": self.google_calendar.to_json(),
            "gmail": self.gmail.to_json(),
        }


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_google_bot_modules() -> tuple[Any, Any, Any, Any]:
    if str(GOOGLE_BOT_ROOT) not in sys.path:
        sys.path.insert(0, str(GOOGLE_BOT_ROOT))

    try:
        from src.google_client import build_calendar_service, build_gmail_service
        from src.oauth_manager import (
            CLIENT_SECRET_FILE,
            TOKEN_FILE,
            GoogleBotAuthMissingError,
            get_google_credentials,
        )
    except ModuleNotFoundError as exc:
        raise ProbeError(
            "Google bot modules are not importable. Make sure the repo code is present and the "
            "Google bot dependencies are installed."
        ) from exc

    return (
        build_calendar_service,
        build_gmail_service,
        get_google_credentials,
        {
            "client_secret_file": CLIENT_SECRET_FILE,
            "token_file": TOKEN_FILE,
            "auth_missing_error": GoogleBotAuthMissingError,
        },
    )


def run_probe() -> tuple[ProbeResult, dict[str, Any]]:
    """Run the repo-managed Google bot auth probe."""
    (
        build_calendar_service,
        build_gmail_service,
        get_google_credentials,
        metadata,
    ) = _load_google_bot_modules()

    try:
        get_google_credentials()
    except metadata["auth_missing_error"] as exc:
        unauthenticated = ConnectorStatus.from_values(
            status="unauthenticated",
            message=str(exc),
        )
        return ProbeResult(google_calendar=unauthenticated, gmail=unauthenticated), metadata

    gmail_status: ConnectorStatus
    calendar_status: ConnectorStatus

    try:
        gmail_service = build_gmail_service()
        profile = gmail_service.users().getProfile(userId="me").execute()
        email = _clean_optional_text(profile.get("emailAddress"))
        gmail_status = ConnectorStatus.from_values(
            status="connected",
            email=email,
            display_name=email,
            message="connected",
        )
    except Exception as exc:
        gmail_status = ConnectorStatus.from_values(status="error", message=str(exc))

    try:
        calendar_service = build_calendar_service()
        calendars = calendar_service.calendarList().list(maxResults=50).execute().get("items") or []
        primary_calendar = next(
            (
                item
                for item in calendars
                if isinstance(item, dict)
                and item.get("primary")
                and isinstance(item.get("id"), str)
            ),
            None,
        )
        calendar_email = (
            _clean_optional_text(
                (primary_calendar or {}).get("id") if isinstance(primary_calendar, dict) else None
            )
            or gmail_status.email
        )
        calendar_display = (
            _clean_optional_text(
                (primary_calendar or {}).get("summary")
                if isinstance(primary_calendar, dict)
                else None
            )
            or calendar_email
        )
        calendar_status = ConnectorStatus.from_values(
            status="connected",
            email=calendar_email,
            display_name=calendar_display,
            message=f"{len(calendars)} calendars visible",
        )
    except Exception as exc:
        calendar_status = ConnectorStatus.from_values(status="error", message=str(exc))

    return ProbeResult(google_calendar=calendar_status, gmail=gmail_status), metadata


def build_text_report(
    probe_result: ProbeResult,
    *,
    expected_email: str | None,
    metadata: dict[str, Any],
) -> str:
    """Render a human-readable status report."""
    lines = [
        "ATLAS Google bot auth status",
        f"Client secret file: {metadata['client_secret_file']}",
        f"Token file: {metadata['token_file']}",
        f"Google Calendar: {_format_connector_status(probe_result.google_calendar)}",
        f"Gmail: {_format_connector_status(probe_result.gmail)}",
    ]

    if expected_email:
        lines.append(f"Expected bot account: {expected_email}")

    if probe_result.all_connected() and probe_result.matches_email(expected_email):
        lines.append("Result: ready")
        return "\n".join(lines)

    lines.append("Result: needs setup")
    lines.extend(_build_next_steps(expected_email))
    return "\n".join(lines)


def _format_connector_status(status: ConnectorStatus) -> str:
    if status.status == "connected":
        identity = status.display_name or status.email or "connected"
        if status.email and status.display_name and status.email not in status.display_name:
            return f"connected as {status.display_name} <{status.email}>"
        if status.email:
            return f"connected as {identity}"
        return f"connected ({identity})"

    detail = status.message or status.status
    return f"{status.status} ({detail})"


def _build_next_steps(expected_email: str | None) -> list[str]:
    lines = [
        "Next step:",
        "1. Run `python3 mcp-servers/google_bot/oauth_setup.py --client-secret-file <path>`.",
        "2. Sign into Google as the bot account during the OAuth browser flow.",
    ]
    if expected_email:
        lines.append(f"3. Make sure the authorized Google account is `{expected_email}`.")
    lines.append(
        "4. Rerun `python3 check_google_bot_auth.py"
        + (f" --expected-email {expected_email}" if expected_email else "")
        + "`."
    )
    lines.append("5. Restart ATLAS after the checker reports `Result: ready`.")
    return lines


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-email",
        help="Google account email that ATLAS should be using for both Gmail and Calendar.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the normalized result as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected_email = _clean_optional_text(args.expected_email)

    try:
        result, metadata = run_probe()
    except ProbeError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(
                f"ATLAS Google bot auth status\nResult: probe failed\nReason: {exc}",
                file=sys.stderr,
            )
        return 2

    ready = result.all_connected() and result.matches_email(expected_email)

    if args.json:
        print(
            json.dumps(
                {
                    "client_secret_file": str(metadata["client_secret_file"]),
                    "token_file": str(metadata["token_file"]),
                    "expected_email": expected_email,
                    "result": result.to_json(),
                    "ready": ready,
                },
                indent=2,
            )
        )
    else:
        print(build_text_report(result, expected_email=expected_email, metadata=metadata))

    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
