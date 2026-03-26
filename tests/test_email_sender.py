"""
tests/test_email_sender.py — Tests for email delivery.

Uses mocking so no real emails are sent during testing.
Run with: pytest tests/test_email_sender.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from delivery.email_sender import send_briefing_email, _render_html, _render_plain


SAMPLE_BRIEFING = """This week is busy but manageable.

Key events:
- Soccer practice Tuesday at 4pm. Leave by 3:35pm, 25 min drive.
- Pediatrician Thursday 10am. Bring insurance card.
- Spring concert Friday 6pm at Jefferson Elementary.

Prep list:
- Wash soccer cleats by Monday night
- Confirm insurance card is in wallet
- Arrive at concert by 5:45pm for seating
"""


def test_render_html_contains_briefing_content():
    """HTML output should contain the briefing text."""
    html = _render_html(SAMPLE_BRIEFING, "March 25, 2026")
    assert "Soccer practice" in html
    assert "Pediatrician" in html
    assert "March 25, 2026" in html
    assert "Weekly Family Briefing" in html


def test_render_html_is_valid_structure():
    """HTML should have basic structural elements."""
    html = _render_html(SAMPLE_BRIEFING, "March 25, 2026")
    assert "<html" in html
    assert "</html>" in html
    assert "<body" in html
    assert "Anchor" in html


def test_render_plain_contains_content():
    """Plain text output should contain the briefing and metadata."""
    plain = _render_plain(SAMPLE_BRIEFING, "March 25, 2026")
    assert "Soccer practice" in plain
    assert "March 25, 2026" in plain
    assert "Anchor" in plain


@patch("delivery.email_sender.smtplib.SMTP_SSL")
def test_send_briefing_email_success(mock_smtp):
    """Email sends successfully with valid credentials."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    result = send_briefing_email(SAMPLE_BRIEFING)

    assert result is True
    mock_server.login.assert_called_once()
    mock_server.sendmail.assert_called_once()


@patch("delivery.email_sender.smtplib.SMTP_SSL")
def test_send_briefing_email_auth_failure(mock_smtp):
    """Returns False and logs error on auth failure — does not crash pipeline."""
    import smtplib
    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    result = send_briefing_email(SAMPLE_BRIEFING)

    assert result is False


@patch("delivery.email_sender.smtplib.SMTP_SSL")
def test_send_briefing_email_smtp_error(mock_smtp):
    """Returns False on general SMTP errors — does not crash pipeline."""
    import smtplib
    mock_smtp.side_effect = smtplib.SMTPException("Connection refused")

    result = send_briefing_email(SAMPLE_BRIEFING)

    assert result is False
