"""Generate a professional email from (Intent, Key Facts, Tone) using a chosen model.

`EmailGenerator` runs the advanced prompt through `config.generate` and parses the
deliverable out of the `<email>` block. Parsing is isolated in `parse_email` so it can be
unit-tested without any API call.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from email_assistant import config
from email_assistant.models import MODELS
from email_assistant.prompts import (
    EMAIL_CLOSE,
    EMAIL_OPEN,
    SYSTEM_PROMPT,
    THINKING_CLOSE,
    THINKING_OPEN,
    build_user_message,
)

_EMAIL_RE = re.compile(re.escape(EMAIL_OPEN) + r"(.*?)" + re.escape(EMAIL_CLOSE), re.DOTALL)
_THINKING_RE = re.compile(
    re.escape(THINKING_OPEN) + r"(.*?)" + re.escape(THINKING_CLOSE), re.DOTALL
)
_SUBJECT_RE = re.compile(r"^\s*Subject:\s*(.+)$", re.MULTILINE)


@dataclass
class GeneratedEmail:
    """The parsed result of one generation."""

    model_key: str
    subject: str
    body: str
    email_text: str  # the full parsed <email> content (subject + body)
    thinking: str  # the <thinking> reasoning (kept for inspection, not scored)
    raw: str  # the unparsed model response


def parse_email(raw: str) -> tuple[str, str, str, str]:
    """Parse a model response into (email_text, subject, body, thinking).

    Falls back gracefully if the model omits the `<email>` tags: the `<thinking>` block is
    stripped and the remainder is treated as the email.
    """
    think_match = _THINKING_RE.search(raw)
    thinking = think_match.group(1).strip() if think_match else ""

    # Prefer the explicit <email> block; otherwise fall back to the response with its
    # <thinking> block and any stray, unclosed email tags removed.
    email_match = _EMAIL_RE.search(raw)
    if email_match:
        email_text = email_match.group(1).strip()
    else:
        without_thinking = _THINKING_RE.sub("", raw)
        email_text = without_thinking.replace(EMAIL_OPEN, "").replace(EMAIL_CLOSE, "").strip()

    subject_match = _SUBJECT_RE.search(email_text)
    if subject_match:
        subject = subject_match.group(1).strip()
        body = email_text[subject_match.end() :].strip()
    else:
        subject = ""
        body = email_text

    return email_text, subject, body, thinking


class EmailGenerator:
    """Generates emails with one configured model."""

    def __init__(self, model_key: str):
        if model_key not in MODELS:
            raise ValueError(f"unknown model {model_key!r}; choose from {list(MODELS)}")
        self.model_key = model_key

    def generate(self, intent: str, key_facts: Sequence[str], tone: str) -> GeneratedEmail:
        user = build_user_message(intent, key_facts, tone)
        raw = config.generate(self.model_key, SYSTEM_PROMPT, user)
        email_text, subject, body, thinking = parse_email(raw)
        return GeneratedEmail(
            model_key=self.model_key,
            subject=subject,
            body=body,
            email_text=email_text,
            thinking=thinking,
            raw=raw,
        )
