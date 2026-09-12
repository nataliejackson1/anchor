"""
agent/briefing.py — Formats the agent's output into a deliverable digest.

Right now: prints to terminal + saves to a local file.
Phase 5 will add email delivery on top of this.
"""

import logging
from datetime import datetime
from pathlib import Path
from config import settings

log = logging.getLogger(__name__)

BRIEFINGS_DIR = Path("briefings")


def render_briefing(briefing_text: str) -> str:
    """
    Wrap the agent's briefing text in a clean format.
    Returns the final string and saves it to a local file.
    """
    now = datetime.now()
    week_of = now.strftime("%B %d, %Y")
    briefing_title = settings.briefing_title
    header = f"""
╔══════════════════════════════════════════════════════╗
  📅  {briefing_title} — Week of {week_of}
╚══════════════════════════════════════════════════════╝
Generated: {now.strftime("%A %B %d at %-I:%M %p")}

"""
    footer = f"""

──────────────────────────────────────────────────────
  {briefing_title}
──────────────────────────────────────────────────────
"""
    full_briefing = header + briefing_text + footer

    # Save to local file — useful for reviewing past briefings
    _save_briefing(full_briefing, now)

    return full_briefing


def _save_briefing(text: str, dt: datetime):
    """Save briefing to briefings/ directory with a datestamped filename."""
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    filename = BRIEFINGS_DIR / f"briefing_{dt.strftime('%Y-%m-%d')}.txt"
    filename.write_text(text)
    log.info(f"Briefing saved to {filename}")
