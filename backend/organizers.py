from fastapi import APIRouter, HTTPException
from storage import get_all_tickets

router = APIRouter()

@router.get("/organizer/events")
def get_organizer_events(email: str):
    tickets = get_all_tickets()
    user_events = {}
    for t in tickets:
        if t["email"] == email:
            event_name = t.get("event_name", f"Event #{t.get('ticket_number', 'N/A')}")
            if event_name not in user_events:
                user_events[event_name] = {
                    "event_name": event_name,
                    "tickets": []
                }
            user_events[event_name]["tickets"].append({
                "ticket_number": t.get("ticket_number"),
                "attendee_email": t.get("email"),
                "date": t.get("date")
            })
    return list(user_events.values())

@router.get("/organizer/event-attendees")
def get_event_attendees(event_name: str):
    tickets = get_all_tickets()
    attendees = []
    for t in tickets:
        if t.get("event_name") == event_name:
            attendees.append({
                "ticket_number": t.get("ticket_number"),
                "attendee_email": t.get("email"),
                "date": t.get("date")
            })
    if not attendees:
        raise HTTPException(status_code=404, detail="No attendees found for this event")
    return attendees
