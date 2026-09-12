"""
delivery/email_sender.py — Sends the weekly briefing as a formatted HTML email.

Uses Gmail SMTP with an app password (no new services needed).
Plain text fallback included for email clients that don't render HTML.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
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
        week_of = datetime.now().strftime("%B %d, %Y")
        subject = f"📅 Weekly Family Briefing — {week_of}"

        html_body = _render_html(briefing_text, week_of)
        plain_body = _render_plain(briefing_text, week_of)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.email_sender
        msg["To"]      = settings.email_recipient

        # Attach plain text first, HTML second
        # Email clients use the last part they can render (HTML preferred)
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.email_sender, settings.gmail_app_password)
            server.sendmail(
                settings.email_sender,
                settings.email_recipient,
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


def _render_html(briefing_text: str, week_of: str) -> str:
    """Render briefing as clean HTML email."""
    paragraphs = briefing_text.strip().split("\n\n")
    html_paragraphs = ""
    for para in paragraphs:
        para_html = para.strip().replace("\n", "<br>")
        lines = para.split("\n")
        if len(lines) == 1 and para.endswith(":") and len(para) < 60:
            html_paragraphs += f'<h3 style="color:#1F4E79; margin-top:24px; margin-bottom:8px;">{para_html}</h3>'
        else:
            html_paragraphs += f'<p style="margin:0 0 16px 0; line-height:1.6;">{para_html}</p>'

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f5f7fa; font-family:Arial, sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa; padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%;">

          <!-- Header -->
          <tr>
            <td style="background-color:#1F4E79; border-radius:8px 8px 0 0; padding:32px;">
              <p style="margin:0; font-size:28px;">📅</p>
              <h1 style="margin:8px 0 4px 0; color:#ffffff; font-size:22px; font-weight:bold;">
                Weekly Family Briefing
              </h1>
              <p style="margin:0; color:#BDD7EE; font-size:14px;">
                Week of {week_of}
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background-color:#ffffff; padding:32px; color:#333333; font-size:15px;">
              {html_paragraphs}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f0f4f8; border-radius:0 0 8px 8px; padding:20px 32px;">
              <p style="margin:0; color:#888888; font-size:12px; text-align:center;">
                Anchor — Family Chaos Orchestrator<br>
                Generated {datetime.now().strftime("%A, %B %d at %-I:%M %p")}
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


def _render_plain(briefing_text: str, week_of: str) -> str:
    """Plain text fallback for email clients that don't render HTML."""
    return f"""Weekly Family Briefing — Week of {week_of}
{'=' * 50}

{briefing_text}

{'=' * 50}
Anchor — Family Chaos Orchestrator
Generated {datetime.now().strftime("%A, %B %d at %-I:%M %p")}
"""
