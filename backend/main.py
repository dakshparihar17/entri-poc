from fastapi import FastAPI ,Request ,Response, HTTPException, Query
from fastapi.responses import FileResponse,JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from passporteye import read_mrz
from passporteye.mrz.text import MRZ
from passlib.context import CryptContext
from storage import save_user, get_user_by_email
from pydantic import BaseModel
import qrcode
from datetime import datetime
import json
import os
import face_recognition
import hashlib
import shutil
from PIL import Image
from pathlib import Path
from blockchain import Blockchain
from storage import save_ticket , get_tickets_by_email
from organizers import router as organiser_router
from organizers import router


app = FastAPI()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

frontend_path = BASE_DIR.parent / "frontend"
tickets_path = BASE_DIR / "tickets"
tickets_path.mkdir(exist_ok=True)
live_faces_dir = BASE_DIR / "live_faces"
live_faces_dir.mkdir(exist_ok=True)
faces_dir_path = BASE_DIR / "faces"
faces_dir_path.mkdir(exist_ok=True)
app.mount("/backend", StaticFiles(directory=Path(__file__).parent), name="backend")


# Routes
app.include_router(organiser_router)


# Initialize Blockchain
blockchain = Blockchain()

# Serve frontend files
@app.get("/")
def root():
    return FileResponse(frontend_path/ "homepage.html")

@app.get("/issue.html")
def issue_ticket_page():
    return FileResponse(frontend_path / "issue.html")  

@app.get("/signup.html")
def signup_page():
    return FileResponse(frontend_path / "signup.html")  

@app.get("/login.html")
def signup_page():
    return FileResponse(frontend_path / "login.html")  

@app.get("/homepage.html")
def homepage():
    return FileResponse(frontend_path / "homepage.html")

@app.get("/index.html")
def read_index():
    return FileResponse(frontend_path / "index.html")  

@app.get("/dashboard.html")
def client_dashboard():
    return FileResponse(frontend_path / "dashboard.html")  

@app.get("/organizer.html")
def organizer_dashboard():
    return FileResponse( frontend_path / "organizer.html")

@app.get("/compliance.html")
def compliance_page():
    return FileResponse(frontend_path / "compliance.html")

@app.get("/martyn-law.html")
def martyn_law_page():
    return FileResponse(frontend_path / "martyn-law.html")

@app.get("/googleb4a7924049f608d6.html")
def google_site_verification():
    return FileResponse(frontend_path / "googleb4a7924049f608d6.html")

@app.get("/martyn-law-checklist.html")
def martyn_law_checklist_page():
    return FileResponse(frontend_path / "martyn-law-checklist.html")

@app.get("/events")
def get_all_events():

    events = load_json("events.json")
    return events

# Serve static files
app.mount("/static", StaticFiles(directory=frontend_path), name="static")
app.mount("/assets", StaticFiles(directory=Path(__file__).parent.parent / "assets"), name="assets")
app.mount("/tickets", StaticFiles(directory=tickets_path), name="tickets")
app.mount("/faces", StaticFiles(directory=faces_dir_path), name="faces")
app.mount("/live_faces", StaticFiles(directory=live_faces_dir), name="live_faces")


# Ticket data model
class TicketRequest(BaseModel):
    user_email: str
    ticket_id: str
    event_code: str

uploads_path = Path(__file__).parent / "uploads"
uploads_path.mkdir(exist_ok=True)

@app.post("/issue.html")
def issue_ticket(data: TicketRequest):
    # Load events
    events = load_json("events.json")

    # Verify event_code exists
    event = next((e for e in events if e["event_code"] == data.event_code), None)
    if not event:
        raise HTTPException(status_code=404, detail="Invalid event code. Please check and try again.")

    # Generate unique hash for backend reference
    ticket_id_raw = f"{data.user_email}-{data.ticket_id}-{data.event_code}"
    unique_ticket_hash = hashlib.sha256(ticket_id_raw.encode()).hexdigest()

    # Generate QR code
    qr = qrcode.make(unique_ticket_hash)
    qr_path = tickets_path / f"{unique_ticket_hash}.png"
    qr.save(qr_path)

    # Create ticket record
    ticket_data = {
        "email": data.user_email,
        "event_code": data.event_code,
        "event_name": event["event_name"],  # pulled from events.json
        "ticket_id": data.ticket_id,
        "date": datetime.now().isoformat(),
        "qr_code_url": f"/tickets/{unique_ticket_hash}.png",
        "organizer_email": event["organizer_email"]
    }

    save_ticket(ticket_data)

    return {
        "message": f"Ticket issued for {event['event_name']} successfully!",
        "event_code": data.event_code,
        "ticket_number": data.ticket_id,
        "date_added": ticket_data["date"]
    }

users_file = DATA_DIR / "users.json"
faces_dir = faces_dir_path



def load_users():
    if users_file.exists():
        with open(users_file, "r") as f:
            return json.load(f)
    return []

@app.post("/check-email")
async def check_email(request: Request):
    data = await request.json()
    email = data.get("email")
    
    users = load_users()
    organizers = load_json("organizers.json")  # Load organizers too
    
    exists = any(u["email"] == email for u in users) or any(o["email"] == email for o in organizers)
    return {"exists": exists}


CURRENT_USER = {"email": "test@example.com"}

@app.get("/user/current")
def get_current_user(request: Request):
    # Read the email from the cookie set during login
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    # Optional: check if user exists
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"email": email}

@app.get("/user/profile")
def get_user_profile(request: Request):
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    user = get_user_by_email(email)
    if not user:
        # fallback: check organizers
        organizers = load_json("organizers.json")
        organizer = next((o for o in organizers if o["email"] == email), None)
        if organizer:
            return {
                "email": organizer["email"],
                "name": organizer["name"],
                "role": "organizer"
            }
        raise HTTPException(status_code=404, detail="User not found")

    face_url = None
    if user.get("live_face_path"):
        face_url = str(request.base_url) + f"live_faces/{Path(user['live_face_path']).name}"

    return {
        "email": user["email"],
        "mrz": user.get("mrz", {}),
        "cropped_face_url": face_url,
        "id_verified": user.get("id_verified", False),
        "personal_details": user.get("personal_details", {}),
        "role": "user"
    }


@app.post("/user/personal-details")
async def update_personal_details(request: Request):
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    data = await request.json()
    allowed = {"full_name", "phone", "dob", "city"}
    details = {k: v for k, v in data.items() if k in allowed}

    users = load_users()
    for u in users:
        if u["email"] == email:
            u["personal_details"] = details
            break
    with open(users_file, "w") as f:
        json.dump(users, f, indent=4)

    return {"message": "Personal details saved."}


@app.get("/user/face")
def get_user_face(email: str):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cropped_face_path = user.get("cropped_face_path")
    if not cropped_face_path or not os.path.exists(cropped_face_path):
        raise HTTPException(status_code=404, detail="Cropped face not found")
    # Serve the image file
    return FileResponse(cropped_face_path)



@app.get("/user/mrz")
def get_mrz(email: str):
    """Return MRZ details for the given user."""
    user = get_user_by_email(email)
    if not user:
        return JSONResponse(status_code=404, content={"message": "User not found"})
    return user.get("mrz", {})

@app.get("/user/tickets")
def get_tickets(request: Request):
    """Return tickets for the currently logged-in user, enriched with event details."""
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    user_tickets = get_tickets_by_email(email)
    if not user_tickets:
        return []

    events = load_json("events.json")
    events_map = {e["event_code"]: e for e in events}

    selfie_filename = f"{email.replace('@','_').replace('.','_')}_live.jpg"
    has_selfie = (live_faces_dir / selfie_filename).exists()

    for t in user_tickets:
        t["ticket_number"] = t["ticket_id"][-6:].upper()
        ev = events_map.get(t["event_code"], {})
        t["event_date"] = ev.get("date", "")
        t["event_location"] = ev.get("location") or ev.get("venue", "")
        t["has_selfie"] = has_selfie

    return user_tickets
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def load_json(filename):
    path = DATA_DIR / filename if not Path(filename).is_absolute() else Path(filename)
    with open(path, "r") as f:
        return json.load(f)

@app.post("/login")
async def login_user(request: Request):
    data = await request.json()
    email = data.get("email").strip().lower()  # normalize
    password = data.get("password")

    users = load_json("users.json")
    organizers = load_json("organizers.json")

    # Case-insensitive search
    user = next((u for u in users if u["email"].strip().lower() == email), None)
    organizer = next((o for o in organizers if o["email"].strip().lower() == email), None)

    response = JSONResponse(content={})

    def verify_password(plain: str, stored: str) -> bool:
        if stored.startswith("$2b$") or stored.startswith("$2a$"):
            return pwd_context.verify(plain, stored)
        return plain == stored

    if user:
        if not verify_password(password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Set cookie here
        response = JSONResponse(content={"redirect": "/dashboard.html", "role": "user"})
        response.set_cookie(key="user_email", value=user["email"], httponly=True)
        return response

    elif organizer:
        if not verify_password(password, organizer["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        response = JSONResponse(content={"redirect": "/organizer.html", "role": "organizer"})
        response.set_cookie(key="user_email", value=organizer["email"], httponly=True)
        return response


    else:
        raise HTTPException(status_code=404, detail="Account not found")

@app.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(key="user_email")
    return response

@app.post("/signup.html")
async def signup(response: Response, email: str = Form(...), password: str = Form(...)):
    if get_user_by_email(email):
        return JSONResponse(status_code=400, content={"message": "User already registered"})

    hashed_password = pwd_context.hash(password)
    save_user({
        "email": email,
        "password": hashed_password,
        "mrz": {},
        "id_verified": False,
        "cropped_face_path": None
    })

    response.set_cookie(key="user_email", value=email, httponly=True)
    return {"message": "User registered successfully"}


@app.post("/user/verify-id")
async def verify_id(request: Request, id_image: UploadFile = File(...)):
    """Step 1 of identity verification: upload ID, extract MRZ + face crop."""
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    file_path = uploads_path / id_image.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(id_image.file, f)

    mrz = read_mrz(str(file_path))
    if not mrz:
        return JSONResponse(status_code=400, content={"message": "MRZ not detected. Please upload a clearer image."})
    mrz_data = mrz.to_dict()

    image = face_recognition.load_image_file(str(file_path))
    face_locations = face_recognition.face_locations(image)
    if not face_locations:
        return JSONResponse(status_code=400, content={"message": "No face detected in uploaded image."})

    top, right, bottom, left = face_locations[0]
    face_image = image[top:bottom, left:right]
    pil_image = Image.fromarray(face_image)
    face_filename = f"{email.replace('@','_').replace('.','_')}_face.jpg"
    face_save_path = faces_dir / face_filename
    pil_image.save(face_save_path)

    users = load_users()
    for u in users:
        if u["email"] == email:
            u["mrz"] = mrz_data
            u["id_image_path"] = str(file_path)
            u["cropped_face_path"] = str(face_save_path)
            break
    with open(users_file, "w") as f:
        json.dump(users, f, indent=4)

    return {"message": "ID processed. Please take a selfie to complete verification.", "mrz": mrz_data}


@app.post("/user/verify-id/selfie")
async def verify_id_selfie(request: Request, live_face: UploadFile = File(...)):
    """Step 2 of identity verification: compare selfie against ID face."""
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    user = get_user_by_email(email)
    if not user or not user.get("cropped_face_path"):
        raise HTTPException(status_code=400, detail="Please upload your ID photo first.")

    live_face_filename = f"{email.replace('@','_').replace('.','_')}_live.jpg"
    live_face_path = live_faces_dir / live_face_filename
    with open(live_face_path, "wb") as f:
        shutil.copyfileobj(live_face.file, f)

    try:
        cropped_image = face_recognition.load_image_file(user["cropped_face_path"])
        live_image = face_recognition.load_image_file(str(live_face_path))
    except Exception as e:
        live_face_path.unlink(missing_ok=True)
        return JSONResponse(status_code=400, content={"message": f"Error loading images: {str(e)}"})

    cropped_encodings = face_recognition.face_encodings(cropped_image)
    live_encodings = face_recognition.face_encodings(live_image)

    if not cropped_encodings:
        live_face_path.unlink(missing_ok=True)
        return JSONResponse(status_code=400, content={"message": "No face detected in ID photo."})
    if not live_encodings:
        live_face_path.unlink(missing_ok=True)
        return JSONResponse(status_code=400, content={"message": "No face detected in selfie. Please retake."})

    match = face_recognition.compare_faces([cropped_encodings[0]], live_encodings[0])
    if not match[0]:
        live_face_path.unlink()
        return JSONResponse(status_code=400, content={"message": "Selfie does not match ID photo. Please try again."})

    users = load_users()
    for u in users:
        if u["email"] == email:
            u["id_verified"] = True
            u["live_face_path"] = str(live_face_path)
            break
    with open(users_file, "w") as f:
        json.dump(users, f, indent=4)

    return {"message": "Identity verified successfully!"}


@app.post("/user/selfie")
async def save_event_selfie(request: Request, event_code: str = Form(...), live_face: UploadFile = File(...)):
    """Save event entry selfie. Only allowed within 48 hours of the event."""
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    tickets = get_tickets_by_email(email)
    if not any(t["event_code"] == event_code for t in tickets):
        raise HTTPException(status_code=403, detail="No ticket found for this event.")

    events = load_json("events.json")
    event = next((e for e in events if e["event_code"] == event_code), None)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    event_date_str = event.get("date")
    if event_date_str:
        try:
            event_dt = datetime.fromisoformat(event_date_str)
        except ValueError:
            event_dt = datetime.strptime(event_date_str, "%Y-%m-%d")
        now = datetime.now()
        delta = event_dt - now
        if delta.total_seconds() > 48 * 3600:
            return JSONResponse(status_code=400, content={"message": "Selfie window opens 48 hours before the event."})
        if delta.total_seconds() < 0:
            return JSONResponse(status_code=400, content={"message": "This event has already passed."})

    live_face_filename = f"{email.replace('@','_').replace('.','_')}_live.jpg"
    live_face_path = live_faces_dir / live_face_filename
    with open(live_face_path, "wb") as f:
        shutil.copyfileobj(live_face.file, f)

    users = load_users()
    for u in users:
        if u["email"] == email:
            u["live_face_path"] = str(live_face_path)
            break
    with open(users_file, "w") as f:
        json.dump(users, f, indent=4)

    return {"message": "Entry selfie saved successfully!"}


@app.post("/signup/live-face")
async def save_live_face(email: str = Form(...), live_face: UploadFile = File(...)):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save uploaded live photo temporarily
    live_face_filename = f"{email.replace('@','_').replace('.','_')}_live.jpg"
    live_face_path = live_faces_dir / live_face_filename
    with open(live_face_path, "wb") as f:
        shutil.copyfileobj(live_face.file, f)

    # --- Load images ---
    try:
        cropped_image = face_recognition.load_image_file(user['cropped_face_path'])
        live_image = face_recognition.load_image_file(live_face_path)
    except Exception as e:
        live_face_path.unlink()  # remove invalid upload
        return JSONResponse(status_code=400, content={"message": f"Error loading images: {str(e)}"})

    # --- Detect faces and get encodings ---
    cropped_encodings = face_recognition.face_encodings(cropped_image)
    live_encodings = face_recognition.face_encodings(live_image)

    if not cropped_encodings:
        live_face_path.unlink()
        return JSONResponse(status_code=400, content={"message": "No face detected in ID photo."})

    if not live_encodings:
        live_face_path.unlink()
        return JSONResponse(status_code=400, content={"message": "No face detected in live selfie."})

    # --- Compare faces ---
    match_results = face_recognition.compare_faces([cropped_encodings[0]], live_encodings[0])

    if not match_results[0]:
        live_face_path.unlink()  # remove selfie if it doesn't match
        return JSONResponse(status_code=400, content={"message": "Live selfie does not match ID photo."})

    # --- Save verified live face path ---
    users = load_users()
    for u in users:
        if u["email"] == email:
            u["live_face_path"] = str(live_face_path)
            break

    with open(users_file, "w") as f:
        json.dump(users, f, indent=4)

    return {"message": "Live selfie verified and saved successfully", "live_face_path": str(live_face_path)}


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# def add_organizer(email, password, name):
#     with open("organizers.json", "r") as f:
#         data = json.load(f)
#     hashed = pwd_context.hash(password)
#     data.append({"email": email, "password": hashed, "name": name})
#     with open("organizers.json", "w") as f:
#         json.dump(data, f, indent=2)
#     print(f"✅ Organizer {email} added.")

# add_organizer("eventhost@entriplatform.com", "secure123", "Host One")