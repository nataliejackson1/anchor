"""
agent/agent.py — Core LLM agent loop.

Feeds upcoming events to Groq, gives it tools to call (weather, drive time),
and collects the final reasoning into a structured briefing.

Flow:
  1. Load upcoming events from local DuckDB
  2. Build system prompt with today's context
  3. Run agent loop — Groq calls tools, we execute them, loop until done
  4. Return final briefing text
"""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from groq import Groq
from storage.duckdb_sync import query_events
from agent.tools import get_weather, get_drive_time
from config import settings

log = logging.getLogger(__name__)
client = Groq(api_key=settings.groq_api_key)
model = settings.groq_model

# ── Tool definitions (what Groq sees) ───────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get the weather forecast for a specific date and location. "
                "Use this for any outdoor event, sports practice, or activity "
                "where weather would affect preparation or enjoyment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "ISO date string e.g. '2026-03-15'",
                    },
                    "location": {
                        "type": "string",
                        "description": "City or address e.g. 'Riverview, FL' or 'Riverview Sports Complex, FL'",
                    },
                },
                "required": ["date", "location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drive_time",
            "description": (
                "Get drive time and distance between two locations. "
                "Use this for any event with a location to calculate when to leave. "
                "Always include arrival_time when you know the event start time "
                "so the estimate accounts for traffic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Starting location e.g. 'Riverview, FL'",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination address or name",
                    },
                    "arrival_time": {
                        "type": "string",
                        "description": "ISO datetime of when you need to arrive e.g. '2026-03-15T16:00:00'. Include this whenever you know the event start time.",
                    },
                },
                "required": ["origin", "destination"],
            },
        },
    },
]


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(home_location: str) -> str:
    today = datetime.now(ZoneInfo(settings.calendar_timezone)).strftime("%A, %B %d %Y")
    agent_tone = settings.agent_tone
    work_location = settings.work_location
    school_location = settings.school_location
    daily_routine = settings.daily_routine
    return f"""You are a concise family logistics coordinator with this tone: {agent_tone}
Today is {today}. Home: {home_location}. Work: {work_location}. School: {school_location}.

Family routine:
{daily_routine}

Analyze the calendar for decisions and schedule risks, not general family advice.

Use tools selectively:
- Use get_drive_time only for off-site events where travel is relevant. Do not use it for home_location appointments.
- Use get_weather only for Grant's golf options, weather during Grant's school pickup walk, or outdoor events. For school pickup, use the city or school area, not a street address.
- Swim lessons are indoors and do not need weather analysis.
- Use no more than one weather lookup per date and one drive-time lookup per distinct destination.
- Stop using tools once those relevant decisions are answered.

Rules:
- Report appointments during work hours, but do not call them conflicts solely because they overlap work.
- Only call out a family childcare conflict when both Natalie and Grant are unavailable while either child is home.
- Ignore conflicts between person-specific appointments unless both parents are needed for childcare.
- If a full-day event includes PTO, note that Natalie's normal work commute changes.
- Do not give generic health, safety, bag-packing, or preparedness advice.
- Do not invent tasks or recommendations. Mention an action only when directly supported by the calendar or routine.
- Mention weather only when it changes a decision.
- Use Eastern Time.

Style requirements:
- Tone is a hard requirement, not a suggestion. Every section must sound like a firm military-style family operations brief.
- Use a firm, direct operations-command tone consistent with the configured tone: {agent_tone}.
- Address Natalie or Grant directly when an action is assigned.
- Use phrases such as "MISSION STATUS", "PRIORITY", "ACTION REQUIRED", "UPCOMING INTEL", and "LOGISTICS" throughout the briefing.
- State exactly what needs to happen, who owns it, and when.
- Prefer: "ACTION REQUIRED: Grant, confirm the school pickup plan by Tuesday at 1:00 PM."
- Avoid: "Please remember to make sure everyone is prepared." Use: "GRANT: Confirm the pickup plan by Tuesday at 1:00 PM."
- You have creative leeway to invent original, dry, harmless operations jargon and occasional jokes for personality. Use one or two when they improve the briefing, such as "the calendar has entered the theater of operations," "family logistics are at DEFCON manageable," or "no family logistics casualties expected."
- Humor must be brief, must not change event facts, and must never replace a clear owner, time, or required action.
- Be decisive, practical, and lightly humorous. Never sound apologetic, generic, insulting, or alarmist.
- Keep the tone consistent across every section without explaining the style instructions.

Write a concise briefing under 500 words with exactly these sections:

MISSION STATUS
One or two sentences covering the week's biggest logistics issue, or "No major conflicts.".

ACTION ITEMS
Only decisions, childcare conflicts, schedule changes, or appointments requiring attention. Omit this section when empty.

WEEK AT A GLANCE
One short bullet per important event. Include local date, time, person, location, and drive time only when relevant. Do not repeat events unnecessarily.

WEATHER WINDOWS
Only Grant's best golf opportunities, school-pickup weather warnings, or weather-sensitive outdoor events. Omit this section when empty.

PREP LIST
Only concrete calendar-related actions. Omit this section when empty.

Use plain-text headings and short bullets. Do not use Markdown bold, italics, heading markers, or nested bullets. Leave a blank line between sections. Do not use tables, JSON, long narrative paragraphs, or commentary about tools.
"""


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""
    log.info(f"Executing tool: {tool_name} with input: {tool_input}")

    if tool_name == "get_weather":
        result = get_weather(
            date=tool_input["date"],
            location=tool_input["location"],
        )
    elif tool_name == "get_drive_time":
        result = get_drive_time(
            origin=tool_input["origin"],
            destination=tool_input["destination"],
            arrival_time=tool_input.get("arrival_time"),
        )
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    log.info(f"Tool result: {result}")
    return json.dumps(result)


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent(home_location: str = "Riverview, FL", days_ahead: int = 7) -> str:
    """
    Run the full agent loop and return a weekly briefing string.

    Args:
        home_location: Used as the origin for drive time calculations
        days_ahead:    How many days of events to include in the briefing

    Returns:
        The final briefing text from the agent
    """
    log.info("Starting agent run...")

    # Load upcoming events from local DuckDB
    events = query_events(f"""
        SELECT event_id, title, start_time, end_time, location,
               description, is_all_day, attendees, source
        FROM events
        WHERE start_time >= now()
          AND start_time <= now() + INTERVAL '{days_ahead} days'
        ORDER BY start_time
    """)

    if not events:
        log.warning("No upcoming events found in DuckDB")
        return "No events found for the coming week. Run the ingestion pipeline first."

    log.info(f"Loaded {len(events)} upcoming events")

    # Format events as a readable block for the initial user message
    events_text = _format_events_for_prompt(events)

    # Initial message to the agent
    messages = [
        {"role": "system", "content": _build_system_prompt(home_location)},
        {
            "role": "user",
            "content": f"Here are my upcoming events for the next {days_ahead} days:\n\n{events_text}\n\nPlease analyze these and produce my weekly briefing.",
        }
    ]

    # ── Agent loop ────────────────────────────────────────────────────────────
    # Groq will call tools, we execute them, feed results back, repeat
    # until Groq stops calling tools and gives us a final text response.

    max_iterations = 6  # keep the run within Groq's free-tier token-per-minute limit
    request_max_tokens = 1800
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        log.info(f"Agent iteration {iteration}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                max_tokens=request_max_tokens,
            )
        except Exception as error:
            error_text = str(error)
            if "rate_limit_exceeded" in error_text or "429" in error_text:
                log.warning("Groq rate limit reached; using the event-based briefing fallback")
                return _build_fallback_briefing(events)
            if "output_parse_failed" not in error_text:
                raise

            log.warning(
                "Groq could not parse a tool call; requesting the briefing without more tools"
            )
            response = client.chat.completions.create(
                model=model,
                messages=messages + [{
                    "role": "user",
                    "content": (
                        "Use the event data and tool results already collected. "
                        "Do not call more tools. Write the complete weekly briefing now."
                    ),
                }],
                max_tokens=request_max_tokens,
            )

        message = response.choices[0].message

        # If Groq is done (no more tool calls), return the final text
        if not message.tool_calls:
            final_text = message.content
            if not final_text or not final_text.strip():
                log.warning("Groq completed without text; using fallback briefing")
                return _build_fallback_briefing(events)
            log.info("Agent complete — briefing generated")
            return final_text

        # If Groq wants to call tools, execute them and feed results back
        messages.append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})

        # Execute each tool Groq requested and add results
        for tool_call in message.tool_calls:
            try:
                tool_input = json.loads(tool_call.function.arguments)
                result = _execute_tool(tool_call.function.name, tool_input)
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                log.warning("Invalid tool arguments for %s: %s", tool_call.function.name, error)
                result = json.dumps({"error": f"Invalid tool arguments: {error}"})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    log.warning("Agent hit max iterations; requesting a final briefing without tools")
    try:
        final_response = client.chat.completions.create(
            model=model,
            messages=messages + [{
                "role": "user",
                "content": (
                    "The tool-use limit has been reached. Use the event data and tool results "
                    "already collected. Do not call tools. Write the complete weekly briefing now."
                ),
            }],
            max_tokens=request_max_tokens,
        )
    except Exception as error:
        if "rate_limit_exceeded" in str(error) or "429" in str(error):
            log.warning("Groq rate limit reached during final request; using fallback")
            return _build_fallback_briefing(events)
        raise
    final_text = final_response.choices[0].message.content
    if not final_text or not final_text.strip():
        log.warning("Groq returned an empty final briefing; using fallback")
        return _build_fallback_briefing(events)
    log.info("Agent complete after max-iteration fallback")
    return final_text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_events_for_prompt(events: list[dict]) -> str:
    """Format event dicts into a clean text block for the prompt."""
    lines = []
    for e in events:
        start = e.get("start_time", "")
        if hasattr(start, "strftime"):
            if start.tzinfo is None:
                start = start.replace(tzinfo=ZoneInfo(settings.calendar_timezone))
            else:
                start = start.astimezone(ZoneInfo(settings.calendar_timezone))
            start = start.strftime("%A, %B %d at %-I:%M %p %Z")

        line = f"- {e['title']} | {start}"
        if e.get("location"):
            line += f" | Location: {e['location']}"
        if e.get("description"):
            line += f" | Notes: {e['description']}"
        if e.get("attendees"):
            line += f" | With: {e['attendees']}"
        lines.append(line)

    return "\n".join(lines)


def _build_fallback_briefing(events: list[dict]) -> str:
    """Create a useful briefing when the LLM is temporarily unavailable."""
    tone = settings.agent_tone.lower()
    is_command_tone = any(
        keyword in tone for keyword in ("sergeant", "hard core", "hardcore", "command", "ops")
    )
    mission_line = (
        f"- 🎯 MISSION STATUS: {len(events)} events on deck. Calendar loaded; execute cleanly. The logistics department remains operational."
        if is_command_tone
        else f"- {len(events)} events are scheduled in the next week."
    )
    lines = [
        "MISSION STATUS",
        mission_line,
    ]
    if is_command_tone:
        lines.extend([
            "ACTION ITEMS",
            "- ⚠️ ACTION REQUIRED: Review the week before Monday. Resolve any schedule conflicts before they become a field exercise.",
            "",
        ])
    lines.append("WEEK AT A GLANCE")
    for event in events:
        start = event.get("start_time", "")
        formatted_start = str(start)
        if hasattr(start, "strftime"):
            if start.tzinfo is None:
                start = start.replace(tzinfo=ZoneInfo(settings.calendar_timezone))
            else:
                start = start.astimezone(ZoneInfo(settings.calendar_timezone))
            formatted_start = start.strftime("%a, %b %-d, %-I:%M %p %Z")
        lines.append(f"- 📅 **{event['title']}**")
        lines.append(f"  When: {formatted_start}")
        if event.get("location"):
            lines.append(f"  Where: {event['location']}")
        else:
            lines.append("  Where: Home / no location listed")

    return "\n".join(lines)
