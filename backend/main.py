from fastapi import FastAPI ,Request ,Response, HTTPException, Query
from fastapi.responses import FileResponse,JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from passporteye import read_mrz
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


app = FastAPI()

# Paths
frontend_path = Path(__file__).parent.parent / "frontend"
tickets_path = Path(__file__).parent / "tickets"
tickets_path.mkdir(exist_ok=True)  # Ensure tickets folder exists
live_faces_dir = Path("live_faces")
live_faces_dir.mkdir(exist_ok=True)

# Routes
app.include_router(organiser_router)

# Initialize Blockchain
blockchain = Blockchain()

# Serve frontend files
@app.get("/")
def root():
    return FileResponse(frontend_path / "homepage.html")

@app.get("/issue.html")
def issue_ticket_page():
    return FileResponse(frontend_path / "issue.html")  

@app.get("/signup.html")
def signup_page():
    return FileResponse(frontend_path / "signup.html")  

@app.get("/login.html")
def signup_page():
    return FileResponse(frontend_path / "login.html")  

@app.get("/index.html")
def read_index():
    return FileResponse(frontend_path / "index.html")  

@app.get("/dashboard.html")
def client_dashboard():
    return FileResponse(frontend_path / "dashboard.html")  

@app.get("/organizer.html")
def organizer_dashboard():
    return FileResponse( frontend_path / "organizer.html")  

# Serve static files
app.mount("/static", StaticFiles(directory=frontend_path), name="static")
app.mount("/tickets", StaticFiles(directory=tickets_path), name="tickets")
app.mount("/faces", StaticFiles(directory="faces"), name="faces")
app.mount("/live_faces", StaticFiles(directory="live_faces"), name="live_faces")


# Ticket data model
class TicketRequest(BaseModel):
    user_email: str
    event_name: str
    ticket_id: str

uploads_path = Path(__file__).parent / "uploads"
uploads_path.mkdir(exist_ok=True)

# Issue ticket endpoint
@app.post("/issue.html")
def issue_ticket(data: TicketRequest):
    # Generate unique hash for backend reference (not shown to user)
    ticket_id_raw = f"{data.user_email}-{data.ticket_id}-{data.event_name}"
    unique_ticket_hash = hashlib.sha256(ticket_id_raw.encode()).hexdigest()

    # Optionally generate QR code (kept but not displayed)
    qr = qrcode.make(unique_ticket_hash)
    qr_path = tickets_path / f"{unique_ticket_hash}.png"
    qr.save(qr_path)

    # Save ticket data (simple version: no blockchain or screenshot)
    ticket_data = {
        "email": data.user_email,
        "event_name": data.event_name,
        "ticket_id": data.ticket_id,   # user’s chosen serial/number
        "date": datetime.now().isoformat(),  # date when added
        "qr_code_url": f"/tickets/{unique_ticket_hash}.png"
    }

    save_ticket(ticket_data)

    return {
        "message": "Ticket issued successfully",
        "event_name": data.event_name,
        "ticket_number": data.ticket_id,
        "date_added": ticket_data["date"]
    }


users_file = Path("Users.json")
faces_dir = Path("faces")



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
        "role": "user"
    }


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
    """Return tickets for the currently logged-in user."""
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")

    user_tickets = get_tickets_by_email(email)
    if not user_tickets:
        return []

    # Add readable fields for dashboard
    for t in user_tickets:
        # Example: event name derived from ID (you can later store actual names)
        t["event_name"] = f"{t['event_name'][:6].upper()}"
        t["ticket_number"] = t["ticket_id"][-6:].upper()

    return user_tickets
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def load_json(filename):
    with open(filename, "r") as f:
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

    if user:
        if not pwd_context.verify(password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"redirect": "/dashboard.html", "role": "user"}

    elif organizer:
        if not pwd_context.verify(password, organizer["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"redirect": "/organizer.html", "role": "organizer"}

    else:
        raise HTTPException(status_code=404, detail="Account not found")


@app.post("/signup.html")
async def signup(response: Response,email: str = Form(...), password: str = Form(...), id_image: UploadFile = File(...)):
    # Check if user exists
    if get_user_by_email(email):
        return JSONResponse(status_code=400, content={"message": "User already registered"})
    
    # Save uploaded file
    file_path = uploads_path / id_image.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(id_image.file, f)

    # Read MRZ
    mrz = read_mrz(str(file_path))
    if not mrz:
        return JSONResponse(status_code=400, content={"message": "MRZ not detected. Please upload a clearer image."})
    mrz_data = mrz.to_dict()

    # Verify ID (mock for now)
    verified = True  
    if not verified:
        return JSONResponse(status_code=400, content={"message": "ID verification failed. Please try again."})

    # ---- FACE CROPPING START ----
    image = face_recognition.load_image_file(str(file_path))
    face_locations = face_recognition.face_locations(image)

    cropped_face_path = None
    if face_locations:
        top, right, bottom, left = face_locations[0]  # Take the first face
        face_image = image[top:bottom, left:right]

        pil_image = Image.fromarray(face_image)
        face_filename = f"{email.replace('@','_').replace('.','_')}_face.jpg"
        face_save_path = faces_dir / face_filename
        pil_image.save(face_save_path)

        cropped_face_path = str(face_save_path)
    else:
        return JSONResponse(status_code=400, content={"message": "No face detected in uploaded image."})
    # ---- FACE CROPPING END ----

    # Save user info (including cropped face)
    save_user({
        "email": email,
        "password": password,
        "mrz": mrz_data,
        "id_image_path": str(file_path),
        "cropped_face_path": cropped_face_path
    })

    response.set_cookie(key="user_email", value=email, httponly=True)
    return {
        "message": "User registered successfully",
        "mrz": mrz_data,
        "cropped_face_path": cropped_face_path
    }


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