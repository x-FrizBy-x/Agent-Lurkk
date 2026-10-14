import os
import re
import subprocess
import logging
from typing import Optional, List
import json

from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

from fastapi.middleware.cors import CORSMiddleware

from memory import MemoryStore
from calendar_api import list_events, create_event, delete_event, search_events, parse_start_end

# ---------------------------------------------------------
# Clean Terminal Output
# ---------------------------------------------------------
def clean_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)
# ---------------------------------------------------------
# Logging Setup (Simple Logging)
# ---------------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# FastAPI + CORS
# ---------------------------------------------------------

app = FastAPI(title="AgentLurkk Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # allow all origins
    allow_credentials=True,
    allow_methods=["*"],          # allow OPTIONS, POST, GET, etc.
    allow_headers=["*"],
)

memory_store = MemoryStore(persist_dir="memory_db")

# ---------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: Optional[str] = "default"
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    memory_used: List[str] = []


# ---------------------------------------------------------
# Calendar Intent Detection
# ---------------------------------------------------------

def detect_calendar_intent(user_message: str) -> Optional[str]:
    msg = user_message.lower()

    if any(x in msg for x in ["schedule", "create event", "add event", "put on my calendar"]):
        return "create"

    if any(x in msg for x in ["show my events", "list events", "what's on my calendar", "my schedule"]):
        return "list"

    if any(x in msg for x in ["delete event", "remove event", "cancel event"]):
        return "delete"

    if any(x in msg for x in ["move", "reschedule", "change event"]):
        return "move"

    return None


# ---------------------------------------------------------
# LLaMA‑3.1 via Ollama
# ---------------------------------------------------------

def call_llama3(prompt: str) -> str:
    logger.info(f"LLaMA prompt: {prompt}")

    try:
        result = subprocess.run(
            ["ollama", "run", "llama3.1"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
    except FileNotFoundError:
        logger.error("Ollama executable was not found in PATH")
        raise RuntimeError("The AI model is not available right now. Please make sure Ollama is installed and running.")

    output = result.stdout.strip()

    # Remove terminal control characters
    output = clean_ansi(output)

    logger.info(f"LLaMA response: {output}")

    return output

# ---------------------------------------------------------
# JSON Event Extraction via LLM
# ---------------------------------------------------------

def extract_event_json(user_message: str) -> Optional[dict]:
    prompt = f"""
    You are a calendar extraction API.

    Return ONLY valid JSON.
    Never change the JSON keys.
    
    The response MUST have exactly these fields:
    
    {{
      "title": "string",
      "datetime_text": "string",
      "duration_minutes": number
    }}
    
    Rules:
    - title must describe the event, not the action.
    - Remove words like schedule, create, add, book.
    - datetime_text must contain the user's original date phrase.
    - duration_minutes must ALWAYS be a number.
    - If no duration is provided, use 60.
    
    Examples:
    
    Input:
    Schedule a dinner with Sara tomorrow at 8 pm
    
    Output:
    {{
    "title":"Dinner with Sara",
    "datetime_text":"tomorrow at 8 pm",
    "duration_minutes":60
    }}
    
    Input:
    Book a meeting with John next Monday for 2 hours
    
    Output:
    {{
    "title":"Meeting with John",
    "datetime_text":"next Monday",
    "duration_minutes":120
    }}
    
    For delete actions, extract the name of the event to search for.

    Example:
    "Delete my dinner with Roma"

    returns:

    {{
    "event_query":"Dinner with Roma"
    }}
    
    Now process:
    
    {user_message}
    """

    raw = call_llama3(prompt)
    logger.info(f"Raw JSON from LLM: {raw}")

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1

        if start == -1 or end == 0:
            logger.error("No JSON found in LLaMA response")
            return None

        json_text = raw[start:end]
        event = json.loads(json_text)

        # Normalize wrong keys
        if "title" not in event and "meeting_name" in event:
            event["title"] = event.pop("meeting_name")

        # Normalize duration
        if not event.get("duration_minutes"):
            event["duration_minutes"] = 60

        # Validate
        if "title" in event and "datetime_text" in event:
            return event

        return None

    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        return None

# ---------------------------------------------------------
# Date Formatter
# ---------------------------------------------------------

def format_event_time(date_string):
    if not date_string:
        return "Unknown time"

    try:
        dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.fromisoformat(f"{date_string}T00:00:00")
        except ValueError:
            return str(date_string)

    return dt.strftime("%d %B %Y at %H:%M")


def get_event_start_value(event: dict) -> Optional[str]:
    start = event.get("start") or {}
    return start.get("dateTime") or start.get("date")

# ---------------------------------------------------------
# Memory Helpers
# ---------------------------------------------------------

def get_relevant_memory(query: str) -> List[str]:
    logger.info(f"Searching memory for: {query}")

    try:
        results = memory_store.search(query, n_results=5)
        docs = results.get("documents", [[]])[0]
        logger.info(f"Memory results: {docs}")
        return docs
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        return []


def format_memory_context(docs: List[str]) -> str:
    if not docs:
        return ""
    joined = "\n".join(f"- {d}" for d in docs)
    return f"Relevant past information:\n{joined}\n"


def maybe_store_memory(user_id: str, user_message: str):
    text = f"User({user_id}) said: {user_message}"
    logger.info(f"Storing memory: {text}")
    memory_store.add_memory(text, mtype="conversation")


# ---------------------------------------------------------
# Extract Delete Target
# ---------------------------------------------------------
def extract_delete_target(user_message):

    prompt = f"""
Extract the event name from this delete request.

Return ONLY the event name.
No explanation.
No quotes.

User request:
{user_message}
"""

    raw = call_llama3(prompt)

    logger.info(f"LLaMA response: {raw}")

    event_name = raw.strip()

    # Remove LLaMA extra text
    event_name = event_name.replace("The event name is:", "")
    event_name = event_name.replace('"', "")
    event_name = event_name.strip()

    return event_name

# ---------------------------------------------------------
# Extract Move Details
# ---------------------------------------------------------

def extract_move_details(user_message):
    prompt = f"""
    You are a calendar assistant.

    Extract ONLY ONE event that the user wants to move.

    Return ONLY valid JSON.
    Do not add explanations.
    Do not use markdown.
    Do not return multiple objects.

    Format:

    {{
        "event_query": "",
        "new_datetime": ""
    }}

    Example:

    User:
    Move Dinner with Sara to tomorrow at 8 pm

    Output:
    {{
        "event_query": "Dinner with Sara",
        "new_datetime": "tomorrow at 8 pm"
    }}

    User request:
    {user_message}
    """

    raw = call_llama3(prompt)

    logger.info(f"Move extraction: {raw}")

    # remove possible markdown
    start = raw.find("{")
    end = raw.find("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    json_text = raw[start:end]

    return json.loads(json_text)

# ---------------------------------------------------------
# Calendar Actions
# ---------------------------------------------------------

def handle_calendar_actions(user_message: str) -> Optional[str]:
    intent = detect_calendar_intent(user_message)
    logger.info(f"Calendar intent detected: {intent}")

    if not intent:
        return None

    # LIST EVENTS
    if intent == "list":
        events = list_events()
        logger.info(f"Listing events: {events}")

        if not events:
            return "You have no upcoming events."

        formatted_lines = []
        for e in events:
            event_start = get_event_start_value(e)
            if not event_start:
                continue
            formatted_lines.append(
                f"- {e.get('summary', 'No title')} on {format_event_time(event_start)}"
            )

        if not formatted_lines:
            return "You have no upcoming events."

        return f"Here are your upcoming events:\n" + "\n".join(formatted_lines)

    # CREATE EVENT
    if intent == "create":
        event = extract_event_json(user_message)
        if not event:
            return "I couldn't understand the date. Try something like 'Dinner tomorrow at 6 pm'."

        title = event["title"]

        start, end = parse_start_end(
            event["datetime_text"],
            event.get("duration_minutes", 60)
        )

        if not start:
            return "I couldn't understand the date."

        created = create_event(
            title,
            start.isoformat(),
            end.isoformat()
        )
        return (
    f"Event created: {created.get('summary', title)} "
    f"on {start.strftime('%A, %d %B %Y from %H:%M')}-{end.strftime('%H:%M')}"
)

    # DELETE EVENT
    if intent == "delete":

        event_query = extract_delete_target(user_message)

        logger.info(f"Searching for event: {event_query}")

        events = search_events(event_query)

        if not events:
            return f"I couldn't find '{event_query}'."

        event = events[0]

        delete_event(event["id"])

        return f"Deleted event: {event.get('summary', 'No title')}"

    # MOVE EVENT (still using parse_start_end for now)
    if intent == "move":

        details = extract_move_details(user_message)

        event_query = details["event_query"]
        new_datetime = details["new_datetime"]

        logger.info(f"Looking for event: {event_query}")

        events = search_events(event_query)

        if not events:
            return f"I couldn't find '{event_query}'."

        if len(events) > 1:
            return "I found multiple matching events. Please specify which one."

        event = events[0]

        new_start, new_end = parse_start_end(new_datetime)

        logger.info(
            f"New time: {new_start} - {new_end}"
        )

        if not new_start:
            return "I couldn't understand the new date."

        delete_event(event["id"])

        create_event(
            event.get("summary", "Event"),
            new_start.isoformat(),
            new_end.isoformat()
        )

        logger.info(
            f"Moved {event.get('summary')} to {new_start}"
        )

        return (
            f"Moved '{event.get('summary')}' "
            f"to {new_start.strftime('%d %B %Y at %H:%M')}"
        )
    return None

# ---------------------------------------------------------
# Main Chat Endpoint
# ---------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    logger.info(f"Received message: {req.message}")

    user_message = req.message.strip()

    # 1. Calendar actions FIRST
    calendar_result = handle_calendar_actions(user_message)
    if calendar_result is not None:
        logger.info(f"Calendar action result: {calendar_result}")
        return ChatResponse(response=calendar_result, memory_used=[])

    # 2. Retrieve memory
    relevant_docs = get_relevant_memory(user_message)
    memory_context = format_memory_context(relevant_docs)

    # 3. Build llama3.1 prompt
    prompt = (
        "You are AgentLurkk, an AI assistant.\n"
        "Use memory context if helpful.\n\n"
        f"{memory_context}\n"
        f"User: {user_message}\n"
        "Assistant:"
    )

    # 4. Call llama3.1
    try:
        llm_answer = call_llama3(prompt)
    except RuntimeError as exc:
        return ChatResponse(response=str(exc), memory_used=relevant_docs)

    # 5. Store memory
    maybe_store_memory(req.user_id, user_message)

    return ChatResponse(
        response=llm_answer,
        memory_used=relevant_docs,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
