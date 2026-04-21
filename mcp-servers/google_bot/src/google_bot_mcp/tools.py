"""High-level Gmail and Calendar MCP tools for the ATLAS Google bot server."""

from __future__ import annotations

import base64
import uuid
from email.mime.text import MIMEText
from typing import Any

try:
    from mcp.server.fastmcp import Context
except ModuleNotFoundError:  # pragma: no cover - test environment without MCP installed
    Context = Any

from src.google_client import build_calendar_service, build_gmail_service, get_http_error_type


def _google_error_message(exc: Exception) -> str:
    http_error_type = get_http_error_type()
    if isinstance(exc, http_error_type):
        response = getattr(exc, "resp", None)
        status = getattr(response, "status", "unknown")
        content = getattr(exc, "content", b"")
        if isinstance(content, bytes):
            try:
                decoded = content.decode("utf-8")
            except UnicodeDecodeError:
                decoded = content.decode(errors="ignore")
        else:
            decoded = str(content)
        decoded = decoded.strip()
        return f"Google API request failed (HTTP {status}): {decoded or exc}"
    return str(exc)


def _normalize_headers(headers: list[dict[str, str]] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for header in headers or []:
        name = header.get("name")
        value = header.get("value")
        if isinstance(name, str) and isinstance(value, str):
            normalized[name.lower()] = value
    return normalized


def _decode_body_data(data: str | None) -> str | None:
    if not data:
        return None
    try:
        decoded = base64.urlsafe_b64decode(data.encode("utf-8"))
    except Exception:
        return None
    return decoded.decode("utf-8", errors="ignore") or None


def _extract_text_bodies(payload: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None

    plain_text = None
    html_text = None
    mime_type = payload.get("mimeType")
    body_data = _decode_body_data((payload.get("body") or {}).get("data"))
    if mime_type == "text/plain" and body_data:
        plain_text = body_data
    elif mime_type == "text/html" and body_data:
        html_text = body_data

    for part in payload.get("parts") or []:
        part_plain, part_html = _extract_text_bodies(part)
        if plain_text is None and part_plain:
            plain_text = part_plain
        if html_text is None and part_html:
            html_text = part_html

    return plain_text, html_text


def _extract_attachments(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return attachments

    filename = payload.get("filename")
    body = payload.get("body") or {}
    attachment_id = body.get("attachmentId")
    if isinstance(filename, str) and filename and isinstance(attachment_id, str):
        attachments.append(
            {
                "filename": filename,
                "attachment_id": attachment_id,
                "size": body.get("size"),
                "mime_type": payload.get("mimeType"),
            }
        )

    for part in payload.get("parts") or []:
        attachments.extend(_extract_attachments(part))
    return attachments


def _message_summary(message: dict[str, Any]) -> dict[str, Any]:
    headers = _normalize_headers((message.get("payload") or {}).get("headers"))
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "label_ids": message.get("labelIds") or [],
        "snippet": message.get("snippet"),
        "subject": headers.get("subject"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "cc": headers.get("cc"),
        "date": headers.get("date"),
        "internal_date": message.get("internalDate"),
    }


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    return {
        "id": event.get("id"),
        "calendar_id": event.get("organizer", {}).get("email"),
        "status": event.get("status"),
        "summary": event.get("summary"),
        "description": event.get("description"),
        "location": event.get("location"),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "html_link": event.get("htmlLink"),
        "conference_link": ((event.get("hangoutLink")) or None),
        "attendees": [
            {
                "email": attendee.get("email"),
                "response_status": attendee.get("responseStatus"),
            }
            for attendee in (event.get("attendees") or [])
            if isinstance(attendee, dict)
        ],
    }


def _label_name_map(gmail_service: Any) -> dict[str, str]:
    response = gmail_service.users().labels().list(userId="me").execute()
    label_map: dict[str, str] = {}
    for label in response.get("labels") or []:
        label_id = label.get("id")
        name = label.get("name")
        if isinstance(label_id, str) and isinstance(name, str):
            label_map[name] = label_id
    return label_map


def _ensure_labels(gmail_service: Any, names: list[str], create_missing_labels: bool) -> dict[str, str]:
    label_map = _label_name_map(gmail_service)
    for name in names:
        if name in label_map:
            continue
        if not create_missing_labels:
            raise ValueError(f"Gmail label does not exist: {name}")
        created = (
            gmail_service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        label_id = created.get("id")
        if isinstance(label_id, str):
            label_map[name] = label_id
    return label_map


async def get_profile_tool(context: Context) -> dict[str, Any]:
    """Return the connected Gmail identity plus visible calendars."""
    try:
        gmail_service = build_gmail_service()
        calendar_service = build_calendar_service()
        gmail_profile = gmail_service.users().getProfile(userId="me").execute()
        calendars = calendar_service.calendarList().list(maxResults=50).execute().get("items") or []
        return {
            "email": gmail_profile.get("emailAddress"),
            "messages_total": gmail_profile.get("messagesTotal"),
            "threads_total": gmail_profile.get("threadsTotal"),
            "calendar_count": len(calendars),
            "calendars": [
                {
                    "id": item.get("id"),
                    "summary": item.get("summary"),
                    "access_role": item.get("accessRole"),
                    "primary": bool(item.get("primary", False)),
                }
                for item in calendars
                if isinstance(item, dict)
            ],
        }
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def list_labels_tool(context: Context) -> list[dict[str, Any]]:
    """List Gmail labels with counts."""
    try:
        gmail_service = build_gmail_service()
        response = gmail_service.users().labels().list(userId="me").execute()
        return [
            {
                "id": label.get("id"),
                "name": label.get("name"),
                "type": label.get("type"),
                "messages_total": label.get("messagesTotal"),
                "messages_unread": label.get("messagesUnread"),
                "threads_total": label.get("threadsTotal"),
                "threads_unread": label.get("threadsUnread"),
            }
            for label in (response.get("labels") or [])
            if isinstance(label, dict)
        ]
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def search_emails_tool(
    context: Context,
    *,
    query: str | None,
    max_results: int,
) -> list[dict[str, Any]]:
    """Search Gmail messages and return lightweight summaries."""
    try:
        gmail_service = build_gmail_service()
        response = (
            gmail_service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = []
        for item in response.get("messages") or []:
            message = (
                gmail_service.users()
                .messages()
                .get(
                    userId="me",
                    id=item["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "To", "Cc", "Date"],
                )
                .execute()
            )
            messages.append(_message_summary(message))
        return messages
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def read_email_tool(context: Context, message_id: str) -> dict[str, Any]:
    """Read a Gmail message including decoded body text and attachment metadata."""
    try:
        gmail_service = build_gmail_service()
        message = (
            gmail_service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = message.get("payload") or {}
        plain_text, html_text = _extract_text_bodies(payload)
        summary = _message_summary(message)
        summary.update(
            {
                "plain_text_body": plain_text,
                "html_body": html_text,
                "attachments": _extract_attachments(payload),
            }
        )
        return summary
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def send_email_tool(
    context: Context,
    *,
    to: str,
    subject: str,
    body: str,
    cc: str | None,
    bcc: str | None,
) -> dict[str, Any]:
    """Send a plain-text email from the bot account."""
    try:
        gmail_service = build_gmail_service()
        message = MIMEText(body)
        message["To"] = to
        message["Subject"] = subject
        if cc:
            message["Cc"] = cc
        if bcc:
            message["Bcc"] = bcc

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        sent = gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {
            "id": sent.get("id"),
            "thread_id": sent.get("threadId"),
            "label_ids": sent.get("labelIds") or [],
        }
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def modify_email_labels_tool(
    context: Context,
    *,
    message_ids: list[str],
    add_label_names: list[str] | None,
    remove_label_names: list[str] | None,
    create_missing_labels: bool,
    archive: bool,
) -> list[dict[str, Any]]:
    """Add/remove labels across one or more Gmail messages."""
    try:
        gmail_service = build_gmail_service()
        names_to_ensure = sorted(set((add_label_names or []) + (remove_label_names or [])))
        label_map = _ensure_labels(gmail_service, names_to_ensure, create_missing_labels)

        add_label_ids = [label_map[name] for name in add_label_names or [] if name in label_map]
        remove_label_ids = [
            label_map[name] for name in remove_label_names or [] if name in label_map
        ]
        if archive:
            remove_label_ids = [*remove_label_ids, "INBOX"]

        results: list[dict[str, Any]] = []
        for message_id in message_ids:
            updated = (
                gmail_service.users()
                .messages()
                .modify(
                    userId="me",
                    id=message_id,
                    body={
                        "addLabelIds": add_label_ids,
                        "removeLabelIds": remove_label_ids,
                    },
                )
                .execute()
            )
            results.append(
                {
                    "id": updated.get("id"),
                    "thread_id": updated.get("threadId"),
                    "label_ids": updated.get("labelIds") or [],
                }
            )
        return results
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def archive_emails_tool(context: Context, *, message_ids: list[str]) -> list[dict[str, Any]]:
    """Archive Gmail messages by removing the INBOX label."""
    return await modify_email_labels_tool(
        context,
        message_ids=message_ids,
        add_label_names=None,
        remove_label_names=None,
        create_missing_labels=False,
        archive=True,
    )


async def list_calendars_tool(context: Context, *, max_results: int) -> list[dict[str, Any]]:
    """List calendars visible to the connected bot account."""
    try:
        calendar_service = build_calendar_service()
        response = calendar_service.calendarList().list(maxResults=max_results).execute()
        return [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "description": item.get("description"),
                "time_zone": item.get("timeZone"),
                "access_role": item.get("accessRole"),
                "primary": bool(item.get("primary", False)),
            }
            for item in (response.get("items") or [])
            if isinstance(item, dict)
        ]
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def search_events_tool(
    context: Context,
    *,
    calendar_id: str,
    query: str | None,
    time_min: str | None,
    time_max: str | None,
    max_results: int,
) -> list[dict[str, Any]]:
    """Search Google Calendar events for the requested calendar."""
    try:
        calendar_service = build_calendar_service()
        response = (
            calendar_service.events()
            .list(
                calendarId=calendar_id,
                q=query,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            )
            .execute()
        )
        return [
            _event_summary(event)
            for event in (response.get("items") or [])
            if isinstance(event, dict)
        ]
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def create_event_tool(
    context: Context,
    *,
    title: str,
    start_time: str,
    end_time: str,
    timezone_str: str,
    calendar_id: str,
    attendees: list[str] | None,
    description: str | None,
    location: str | None,
    add_google_meet: bool,
    visibility: str | None,
    transparency: str | None,
) -> dict[str, Any]:
    """Create a Google Calendar event."""
    try:
        calendar_service = build_calendar_service()
        body: dict[str, Any] = {
            "summary": title,
            "start": {"dateTime": start_time, "timeZone": timezone_str},
            "end": {"dateTime": end_time, "timeZone": timezone_str},
        }
        if attendees:
            body["attendees"] = [{"email": email} for email in attendees]
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if visibility:
            body["visibility"] = visibility
        if transparency:
            body["transparency"] = transparency
        if add_google_meet:
            body["conferenceData"] = {"createRequest": {"requestId": uuid.uuid4().hex}}

        request = calendar_service.events().insert(
            calendarId=calendar_id,
            body=body,
            sendUpdates="all",
            conferenceDataVersion=1 if add_google_meet else 0,
        )
        created = request.execute()
        return _event_summary(created)
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def update_event_tool(
    context: Context,
    *,
    event_id: str,
    calendar_id: str,
    title: str | None,
    start_time: str | None,
    end_time: str | None,
    timezone_str: str | None,
    description: str | None,
    location: str | None,
    attendees_to_add: list[str] | None,
    attendees_to_remove: list[str] | None,
    add_google_meet: bool,
    visibility: str | None,
    transparency: str | None,
) -> dict[str, Any]:
    """Update an existing Google Calendar event."""
    try:
        calendar_service = build_calendar_service()
        event = calendar_service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        if title is not None:
            event["summary"] = title
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if visibility is not None:
            event["visibility"] = visibility
        if transparency is not None:
            event["transparency"] = transparency

        if start_time is not None:
            if not timezone_str:
                raise ValueError("timezone_str is required when updating start_time or end_time")
            event["start"] = {"dateTime": start_time, "timeZone": timezone_str}
        if end_time is not None:
            if not timezone_str:
                raise ValueError("timezone_str is required when updating start_time or end_time")
            event["end"] = {"dateTime": end_time, "timeZone": timezone_str}

        attendees = [attendee for attendee in (event.get("attendees") or []) if isinstance(attendee, dict)]
        attendee_by_email = {
            attendee.get("email"): attendee
            for attendee in attendees
            if isinstance(attendee.get("email"), str)
        }
        for email in attendees_to_add or []:
            attendee_by_email.setdefault(email, {"email": email})
        for email in attendees_to_remove or []:
            attendee_by_email.pop(email, None)
        if attendee_by_email:
            event["attendees"] = list(attendee_by_email.values())

        if add_google_meet and not event.get("conferenceData"):
            event["conferenceData"] = {"createRequest": {"requestId": uuid.uuid4().hex}}

        updated = (
            calendar_service.events()
            .update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates="all",
                conferenceDataVersion=1 if add_google_meet else 0,
            )
            .execute()
        )
        return _event_summary(updated)
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise


async def delete_event_tool(context: Context, *, event_id: str, calendar_id: str) -> dict[str, Any]:
    """Delete a Google Calendar event."""
    try:
        calendar_service = build_calendar_service()
        calendar_service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="all").execute()
        return {"deleted": True, "event_id": event_id, "calendar_id": calendar_id}
    except Exception as exc:
        await context.error(_google_error_message(exc))
        raise
