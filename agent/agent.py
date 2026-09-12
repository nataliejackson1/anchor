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
from groq import Groq
from storage.duckdb_sync import query_events
from agent.tools import get_weather, get_drive_time
from config import settings

log = logging.getLogger(__name__)
client = Groq(api_key=settings.groq_api_key)
model = "llama-3.1-8b-instant"

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
    today = datetime.now().strftime("%A, %B %d %Y")
    agent_tone = settings.agent_tone
    work_location = settings.work_location
    school_location = settings.school_location
    daily_routine = settings.daily_routine
    return f"""You are {agent_tone}
Today is {today}. The home base is {home_location}. The work location is {work_location}. The kids' school is {school_location}.

Daily schedule is {daily_routine}.

For every event with a location:
- Call get_drive_time to calculate how long it takes to get there from the home location and when she needs to leave
- Call get_weather if it's an outdoor event or the weather would affect what to bring or wear
- Call get_weather for the home location for each day and give a quick summary of what the week's weather looks like overall

After gathering information with your tools, write a weekly briefing that:
1. Leads with the most important or time-sensitive things this week
2. For each event includes: what it is, when, any drive time or weather considerations, and prep needed
3. Flags any conflicts or tight turnarounds she should know about
4. Ends with a short "prep list" — things to do in advance (buy, pack, prepare)
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

    max_iterations = 10  # safety cap to prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        log.info(f"Agent iteration {iteration}")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            max_tokens=4096,
        )

        message = response.choices[0].message

        # If Groq is done (no more tool calls), return the final text
        if not message.tool_calls:
            final_text = message.content
            log.info("Agent complete — briefing generated")
            return final_text

        # If Groq wants to call tools, execute them and feed results back
        messages.append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})

        # Execute each tool Groq requested and add results
        for tool_call in message.tool_calls:
            tool_input = json.loads(tool_call.function.arguments)
            result = _execute_tool(tool_call.function.name, tool_input)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    log.warning("Agent hit max iterations without completing")
    return "Agent did not complete within the allowed iterations."


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_events_for_prompt(events: list[dict]) -> str:
    """Format event dicts into a clean text block for the prompt."""
    lines = []
    for e in events:
        start = e.get("start_time", "")
        if hasattr(start, "strftime"):
            start = start.strftime("%A %B %d at %-I:%M %p")

        line = f"- {e['title']} | {start}"
        if e.get("location"):
            line += f" | Location: {e['location']}"
        if e.get("description"):
            line += f" | Notes: {e['description']}"
        if e.get("attendees"):
            line += f" | With: {e['attendees']}"
        lines.append(line)

    return "\n".join(lines)
