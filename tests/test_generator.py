"""Offline tests for the email-response parser (no API calls)."""

from email_assistant.generator import parse_email


def test_parses_subject_body_and_thinking():
    raw = (
        "<thinking>\nPlan: greet and thank.\n</thinking>\n"
        "<email>\nSubject: Next steps\n\n"
        "Hi [Name],\n\nThanks for your time.\n\nRegards,\n[Your name]\n</email>"
    )
    email_text, subject, body, thinking = parse_email(raw)
    assert subject == "Next steps"
    assert email_text.startswith("Subject: Next steps")
    assert "Thanks for your time." in body
    assert "Subject:" not in body
    assert "Plan: greet and thank." in thinking


def test_falls_back_when_email_tags_missing():
    raw = "Subject: Plain one\n\nNo tags in this response."
    email_text, subject, body, thinking = parse_email(raw)
    assert subject == "Plain one"
    assert "No tags in this response." in body
    assert thinking == ""


def test_strips_thinking_block_in_fallback():
    raw = "<thinking>internal notes</thinking>\nSubject: X\n\nVisible body."
    email_text, subject, body, thinking = parse_email(raw)
    assert "internal notes" not in email_text
    assert thinking == "internal notes"
    assert subject == "X"


def test_strips_stray_unclosed_email_tag_in_fallback():
    # Malformed response: opening <email> but no closing tag -> fallback must not leak it.
    raw = "<email>\nSubject: Y\n\nBody text without a closing tag."
    email_text, subject, body, thinking = parse_email(raw)
    assert "<email>" not in email_text
    assert subject == "Y"
    assert "Body text without a closing tag." in body
