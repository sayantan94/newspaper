"""Section: the mailbag — top unread Gmail via IMAP + app password.

Setup: `paper auth gmail` (stores the app password in the macOS Keychain).
App passwords: https://myaccount.google.com/apppasswords (needs 2FA on).
No Google Cloud project, no OAuth consent screen.
"""

from __future__ import annotations

import email
import imaplib
from email.header import decode_header

from ..models import Section, SectionItem
from ..secrets import get_secret
from .base import PaperContext, SectionConnector

_HOST = "imap.gmail.com"
_MAX_EMAILS = 8
_SOCKET_TIMEOUT = 8


def _decode(value: str) -> str:
    parts = []
    for text, charset in decode_header(value or ""):
        if isinstance(text, bytes):
            parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts).strip()


def _clean_from(sender: str) -> str:
    sender = _decode(sender)
    if "<" in sender:  # "Jane Doe <jane@x.com>" → "Jane Doe"
        name = sender.split("<")[0].strip().strip('"')
        return name or sender
    return sender


def fetch_unread(address: str, password: str, limit: int = _MAX_EMAILS) -> list[tuple[str, str]]:
    """[(from, subject)] for the newest unread inbox mail. Raises on auth failure."""
    client = imaplib.IMAP4_SSL(_HOST, timeout=_SOCKET_TIMEOUT)
    try:
        client.login(address, password)
        client.select("INBOX", readonly=True)
        _, data = client.search(None, "UNSEEN")
        ids = data[0].split()[-limit:]
        out = []
        for msg_id in reversed(ids):
            _, msg_data = client.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    out.append((_clean_from(msg.get("From", "")), _decode(msg.get("Subject", ""))))
        return out
    finally:
        try:
            client.logout()
        except Exception:
            pass


class GmailConnector(SectionConnector):
    name = "gmail"
    title = "THE MAILBAG"
    timeout = 15.0

    def available(self) -> tuple[bool, str]:
        # config check happens in fetch (needs ctx); cheap static hint here
        return True, ""

    def fetch(self, ctx: PaperContext) -> Section:
        address = ctx.config.gmail_address
        if not address:
            return Section(
                name=self.name,
                title=self.title,
                notice="connect your inbox: paper auth gmail",
            )
        password = get_secret("gmail", address)
        if not password:
            return Section(
                name=self.name,
                title=self.title,
                notice=f"no app password stored for {address} — run: paper auth gmail",
            )
        mails = fetch_unread(address, password)
        items = [SectionItem(title=subject or "(no subject)", meta=sender) for sender, subject in mails]
        if not items:
            items = [SectionItem(title="inbox zero — nothing unread")]
        return Section(name=self.name, title=self.title, items=items)
