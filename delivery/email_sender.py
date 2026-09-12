"""
delivery/email_sender.py — Sends the weekly briefing as a formatted HTML email.

Uses Gmail SMTP with an app password (no new services needed).
Plain text fallback included for email clients that don't render HTML.
"""

import logging
import html
import re
import smtplib
from email.utils import getaddresses
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo
from config import settings

log = logging.getLogger(__name__)


def send_briefing_email(briefing_text: str) -> bool:
    """
    Send the weekly briefing as an HTML email.

    Args:
        briefing_text: Plain text briefing from the agent

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        now = datetime.now(ZoneInfo(settings.calendar_timezone))
        week_of = now.strftime("%B %d, %Y")
        subject = f"📅 Weekly Family Briefing — {week_of}"
        recipients = _parse_recipients(settings.email_recipient)

        html_body = _render_html(briefing_text, week_of)
        plain_body = _render_plain(briefing_text, week_of)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.email_sender
        msg["To"]      = ", ".join(recipients)

        # Attach plain text first, HTML second
        # Email clients use the last part they can render (HTML preferred)
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.email_sender, settings.gmail_app_password)
            server.sendmail(
                settings.email_sender,
                recipients,
                msg.as_string()
            )

        log.info(f"Briefing email sent to {settings.email_recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        log.error(
            "Gmail authentication failed. Check EMAIL_SENDER and GMAIL_APP_PASSWORD in .env. "
        )
        return False


    except smtplib.SMTPException as e:
        log.error(f"SMTP error sending email: {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error sending email: {e}", exc_info=True)
        return False

def _parse_recipients(value: str) -> list[str]:
    """Parse comma-separated email addresses for the SMTP envelope."""
    recipients = [address for _, address in getaddresses([value]) if address]
    if not recipients:
        raise ValueError("EMAIL_RECIPIENT must contain at least one email address")
    return recipients


def _render_html(briefing_text: str, week_of: str) -> str:
  """Render Markdown-like briefing text as structured email HTML."""
  sections = _briefing_sections(briefing_text)
  html_sections = ""
  for title, items, paragraphs in sections:
    content = ""
    if items:
      content += '<ul style="margin:0; padding:0; list-style:none;">'
      for item in items:
        content += (
          '<li style="margin:0 0 12px 0; padding:0 0 12px 16px; '
          'border-bottom:1px solid #e8edf2; line-height:1.55;">'
          f'<span style="color:#d97706; font-size:16px;">•</span>&nbsp;{_format_inline(item)}'
          '</li>'
        )
      content += '</ul>'
    for paragraph in paragraphs:
      content += f'<p style="margin:0 0 12px 0; line-height:1.6;">{_format_inline(paragraph)}</p>'
    html_sections += f'''
      <tr>
      <td style="padding:0 0 20px 0;">
        <h2 style="margin:0 0 12px 0; color:#16324f; font-size:13px; letter-spacing:1.4px; font-weight:bold;">{html.escape(title)}</h2>
        <div style="background:#f8fafc; border-left:4px solid #d97706; padding:16px 18px;">{content}</div>
      </td>
      </tr>'''

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#eef2f5; font-family:'Avenir Next','Segoe UI',Arial,sans-serif; color:#243447;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa; padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px; width:100%;">

          <!-- Header -->
          <tr>
            <td style="background-color:#16324f; border-radius:10px 10px 0 0; padding:30px 32px;">
              <p style="margin:0; color:#f4b942; font-size:12px; letter-spacing:2px; font-weight:bold;">ANCHOR / WEEKLY OPERATIONS</p>
              <h1 style="margin:10px 0 6px 0; color:#ffffff; font-family:Georgia,serif; font-size:28px; line-height:1.2; font-weight:normal;">
                Weekly Family Briefing
              </h1>
              <p style="margin:0; color:#c7d8e6; font-size:14px;">
                Week of {week_of}
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background-color:#ffffff; padding:30px 32px 18px 32px; color:#243447; font-size:15px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {html_sections}
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#e3eaf0; border-radius:0 0 10px 10px; padding:18px 32px;">
              <p style="margin:0; color:#888888; font-size:12px; text-align:center;">
                Anchor — Family Chaos Orchestrator<br>
                Generated {datetime.now(ZoneInfo(settings.calendar_timezone)).strftime("%A, %B %d at %-I:%M %p %Z")}
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
""".strip()


def _briefing_sections(briefing_text: str) -> list[tuple[str, list[str], list[str]]]:
  """Group headings, bullets, and paragraphs from the agent's plain text output."""
  sections = []
  title = "BRIEFING"
  items = []
  paragraphs = []
  for raw_line in briefing_text.strip().splitlines():
    line = raw_line.strip()
    if not line:
      continue
    normalized = line.rstrip(":").upper()
    if normalized in {"MISSION STATUS", "UPCOMING INTEL", "LOGISTICS", "PREP LIST"}:
      if items or paragraphs:
        sections.append((title, items, paragraphs))
      title, items, paragraphs = normalized, [], []
    elif line.startswith(("- ", "– ", "* ")):
      items.append(line[2:].strip())
    else:
      paragraphs.append(line)
  if items or paragraphs:
    sections.append((title, items, paragraphs))
  return sections


def _format_inline(value: str) -> str:
  """Escape text, then render the small Markdown subset used by the agent."""
  escaped = html.escape(value)
  return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _render_plain(briefing_text: str, week_of: str) -> str:
    """Plain text fallback for email clients that don't render HTML."""
    return f"""Weekly Family Briefing — Week of {week_of}
{'=' * 50}

{briefing_text}

{'=' * 50}
Anchor — Family Chaos Orchestrator
Generated {datetime.now(ZoneInfo(settings.calendar_timezone)).strftime("%A, %B %d at %-I:%M %p %Z")}
"""
