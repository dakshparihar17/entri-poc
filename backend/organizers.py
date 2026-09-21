from fastapi import (
    APIRouter, HTTPException, Query, Form, File, UploadFile, FastAPI
)
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from storage import get_all_tickets, load_json, save_json, redeem_ticket
from pathlib import Path
import face_recognition
import tempfile
import json
import os
import uuid
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

router = APIRouter()

# Paths to data files
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

users_path = DATA_DIR / "users.json"
attendance_path = DATA_DIR / "attendance.json"
events_path = DATA_DIR / "events.json"
tickets_path = DATA_DIR / "tickets.json"

# Ensure attendance.json exists
if not attendance_path.exists():
    with open(attendance_path, "w") as f:
        json.dump({}, f)

# ✅ Serve static files (including tickets.json)
app = FastAPI()
app.mount("/backend", StaticFiles(directory=str(BASE_DIR)), name="backend")


@router.get("/tickets.json")
def serve_tickets_json():
    """Serve tickets.json for frontend access."""
    if not tickets_path.exists():
        raise HTTPException(status_code=404, detail="tickets.json not found")
    with open(tickets_path, "r") as f:
        data = json.load(f)
    return data


@router.get("/organizer/events")
def get_organizer_events(email: str = Query(...)):
    """Fetch all events created by a specific organizer along with ticket data."""
    email = email.strip().lower()
    tickets = get_all_tickets()
    events = load_json(events_path)

    organizer_events = [e for e in events if e.get("organizer_email", "").strip().lower() == email]
    if not organizer_events:
        raise HTTPException(status_code=404, detail=f"No events found for organizer {email}")

    result = []
    for event in organizer_events:
        event_code = event.get("event_code")
        event_tickets = [t for t in tickets if t.get("event_code") == event_code]

        result.append({
            "event_code": event_code,
            "event_name": event.get("event_name"),
            "date": event.get("date"),
            "location": event.get("location"),
            "description": event.get("description"),
            "ticket_count": len(event_tickets),
            "tickets": [
                {
                    "ticket_number": t.get("ticket_id"),
                    "attendee_email": t.get("email"),
                    "date": t.get("date")
                }
                for t in event_tickets
            ]
        })

    return result


@router.get("/organizer/event-attendees")
def get_event_attendees(event_code: str = Query(...)):
    """Return all attendees (users) who have tickets for a specific event with full user data."""
    tickets = load_json(tickets_path)
    users = load_json(users_path)

    # Filter tickets for the event
    event_tickets = [t for t in tickets if t.get("event_code") == event_code]
    if not event_tickets:
        raise HTTPException(status_code=404, detail="No attendees found for this event")

    # Merge ticket info with user data
    attendees = []
    for t in event_tickets:
        email = t.get("email")
        user_data = next((u for u in users if u["email"] == email), {})
        mrz_data = user_data.get("mrz", {})
        attendees.append({
            "ticket_number": t.get("ticket_id"),
            "attendee_email": email,
            "date": t.get("date"),
            "name": mrz_data.get("surname"),
            "gender": mrz_data.get("sex")
        })

    return attendees



@router.post("/organizer/create-event")
def create_event(
    event_name: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    description: str = Form(""),
    organizer_email: str = Form(...)
):
    """Creates a new event for the organizer with a unique event code."""
    events = load_json(events_path)
    event_code = f"EVT-{uuid.uuid4().hex[:6].upper()}"

    new_event = {
        "event_code": event_code,
        "event_name": event_name,
        "date": date,
        "location": location,
        "description": description,
        "organizer_email": organizer_email.strip().lower()
    }

    events.append(new_event)
    save_json(events_path, events)
    return {"message": "Event created successfully", "event_code": event_code}

@router.get("/organizer/attendance")
def check_attendance(event_code: str = Query(..., description="Event code")):
    """
    Returns a dictionary mapping attendee emails to their attendance status (True/False)
    for a specific event. This will allow frontend to show ✅ if attended.
    """
    attendance_file = DATA_DIR / "attendance.json"
    tickets = load_json(tickets_path)

    # Load attendance.json
    if attendance_file.exists():
        attendance_data = load_json(attendance_file)
    else:
        attendance_data = {}

    event_attendance = attendance_data.get(event_code, [])
    attended_emails = {entry["email"] for entry in event_attendance}

    # Map all ticket holders to their attendance status
    event_tickets = [t for t in tickets if t.get("event_code") == event_code]
    result = []
    for t in event_tickets:
        result.append({
            "email": t.get("email"),
            "attended": t.get("email") in attended_emails
        })

    return result



@router.post("/organizer/scan-face")
async def scan_face(event_code: str = Form(...), live_image: UploadFile = File(...)):
    """Scan live face image, match with user, and mark attendance."""
    base_dir = os.path.dirname(__file__)
    users_file = str(DATA_DIR / "users.json")
    tickets_file = str(DATA_DIR / "tickets.json")
    attendance_file = str(DATA_DIR / "attendance.json")

    users = load_json(users_file)
    tickets = load_json(tickets_file)
    attendance = load_json(attendance_file)
    if not isinstance(attendance, dict):
        attendance = {}

    temp_path = os.path.join(base_dir, "temp_live.jpg")
    with open(temp_path, "wb") as buffer:
        buffer.write(await live_image.read())

    try:
        live_image_data = face_recognition.load_image_file(temp_path)
        live_encoding = face_recognition.face_encodings(live_image_data)[0]
    except IndexError:
        os.remove(temp_path)
        attendance.setdefault(f"{event_code}_failures", []).append({
            "timestamp": datetime.now().isoformat(), "reason": "no_face_detected"
        })
        save_json(attendance_file, attendance)
        return JSONResponse({"status": "error", "message": "No face detected in the live image."}, status_code=400)

    match_found = False
    recognized_user_email = None

    for user_data in users:
        email = user_data.get("email")
        user_selfie_path = user_data.get("live_face_path")
        if not user_selfie_path or not os.path.exists(user_selfie_path):
            continue

        try:
            known_image = face_recognition.load_image_file(user_selfie_path)
            known_encoding = face_recognition.face_encodings(known_image)[0]
        except Exception:
            continue

        matches = face_recognition.compare_faces([known_encoding], live_encoding, tolerance=0.5)
        if matches[0]:
            match_found = True
            recognized_user_email = email
            break

    os.remove(temp_path)

    if not match_found:
        attendance.setdefault(f"{event_code}_failures", []).append({
            "timestamp": datetime.now().isoformat(), "reason": "no_match"
        })
        save_json(attendance_file, attendance)
        return JSONResponse({
            "status": "fail",
            "message": "No matching user found in the system."
        }, status_code=404)

    user_ticket = next((t for t in tickets if t["email"] == recognized_user_email and t["event_code"] == event_code), None)
    if not user_ticket:
        attendance.setdefault(f"{event_code}_failures", []).append({
            "timestamp": datetime.now().isoformat(), "reason": "no_ticket"
        })
        save_json(attendance_file, attendance)
        return JSONResponse({
            "status": "fail",
            "message": f"User {recognized_user_email} does not have a valid ticket for this event."
        }, status_code=403)

    event_attendance = attendance.get(event_code, [])
    already_attended = recognized_user_email in [entry["email"] for entry in event_attendance]

    if not already_attended:
        event_attendance.append({
            "email": recognized_user_email,
            "timestamp": datetime.now().isoformat()
        })
        attendance[event_code] = event_attendance
        save_json(attendance_file, attendance)
        redeem_ticket(recognized_user_email, event_code)

    total_attendees = len(event_attendance)

    return JSONResponse({
        "status": "success",
        "message": f"Successfully recognized {recognized_user_email}." if not already_attended else f"{recognized_user_email} already admitted.",
        "recognized_user": recognized_user_email,
        "event_code": event_code,
        "current_attendance_count": total_attendees,
        "already_attended": already_attended
    }, status_code=200)


@router.get("/organizer/event-stats")
def get_event_stats(event_code: str = Query(...)):
    """Return entry statistics for an event: expected, arrived, face_id_success, face_id_failed."""
    tickets = load_json(tickets_path)
    att_path = DATA_DIR / "attendance.json"
    attendance_data = load_json(att_path) if att_path.exists() else {}
    if not isinstance(attendance_data, dict):
        attendance_data = {}

    expected = len([t for t in tickets if t.get("event_code") == event_code])
    arrived = len(attendance_data.get(event_code, []))
    face_failed = len(attendance_data.get(f"{event_code}_failures", []))

    return {
        "expected": expected,
        "arrived": arrived,
        "face_id_success": arrived,
        "face_id_failed": face_failed
    }
