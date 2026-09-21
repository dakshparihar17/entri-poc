# Entri — Identity. Simplified.

**Entri** is a next-generation identity and access platform designed for the Gen-Z era.
We're reimagining how people enter events, venues, and digital spaces — where **you are the ticket**.

Built for **events, nightclubs, and stadiums**, Entri combines **blockchain-backed identity**, **AI face verification**, and **frictionless access control** to create a safer, smarter experience for both users and organizers.

---

## What it does

- **Smart ID Verification** — Users sign up by uploading a government ID. The app reads the MRZ (machine-readable zone), crops the face, and stores a verified identity.
- **Live Selfie Matching** — On signup, a live selfie is compared against the ID photo using face recognition. No match = no entry.
- **Blockchain-Backed Tickets** — Each ticket is uniquely hashed and tied to the holder's identity.
- **Organizer Dashboard** — Create events, track real-time attendance, and scan faces for entry — no physical tickets needed.
- **QR Code Entry** — Tickets are issued as QR codes linked to the user's verified identity.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI (Python 3.11), Uvicorn |
| **Frontend** | Vanilla HTML / CSS / JS (no build step) |
| **Face Recognition** | `face-recognition` (dlib-based) |
| **ID Parsing** | PassportEye (MRZ reader) + Tesseract OCR |
| **Storage** | JSON files (flat-file, no database needed for POC) |
| **Auth** | Cookie-based sessions + bcrypt password hashing |
| **Tickets** | QR codes generated server-side |

---

## Prerequisites

You only need two things installed before running setup:

| Requirement | How to check | Install |
|---|---|---|
| **macOS** | — | — |
| **Homebrew** | `brew --version` | [brew.sh](https://brew.sh) |
| **Python 3.11** | `python3.11 --version` | `brew install python@3.11` |

Everything else (system libraries, Python packages, folder structure, data files) is handled automatically by the setup script.

---

## Setup — one command

Clone the repo, then from the **project root** run:

```bash
bash setup.sh
```

That's it. The script will:

1. Install `tesseract` and `cmake` via Homebrew (needed for OCR and face recognition)
2. Create a Python 3.11 virtual environment at `.venv/`
3. Install all Python dependencies from `requirements.txt`
4. Create the required directories (`backend/data/`, `backend/faces/`, `backend/live_faces/`, `backend/tickets/`, `backend/uploads/`)
5. Create empty JSON data files if they don't exist yet
6. Run a health check and confirm everything is ready

> **Note:** The first run may take a few minutes. `dlib` (the face recognition engine) is a large compiled package and pip needs time to download it.

---

## Running the app

After setup completes, start the backend server:

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload
```

Then open your browser at:

```
http://127.0.0.1:8000
```

The frontend is served directly by the backend — no separate server needed.

---

## Project structure

```
entri-poc/
├── setup.sh                  # One-time setup script — run this first
│
├── backend/
│   ├── main.py               # FastAPI app, all routes
│   ├── requirements.txt      # Python dependencies
│   ├── storage.py            # JSON read/write helpers for users & tickets
│   ├── organizers.py         # Organizer routes (events, attendance, face scan)
│   ├── blockchain.py         # Lightweight in-memory blockchain for ticket hashing
│   │
│   ├── data/                 # Runtime data — gitignored, created by setup.sh
│   │   ├── users.json        # Registered users
│   │   ├── organizers.json   # Organizer accounts
│   │   ├── events.json       # Created events
│   │   ├── tickets.json      # Issued tickets
│   │   └── attendance.json   # Event attendance records
│   │
│   ├── faces/                # Cropped ID face images (gitignored)
│   ├── live_faces/           # Verified selfies (gitignored)
│   ├── tickets/              # Generated QR code PNGs (gitignored)
│   └── uploads/              # Uploaded ID images (gitignored)
│
└── frontend/
    ├── homepage.html         # Landing page
    ├── login.html            # Login (user + organizer)
    ├── signup.html           # User registration (ID upload + selfie)
    ├── dashboard.html        # User dashboard (tickets, profile)
    ├── organizer.html        # Organizer dashboard (events, attendance)
    └── issue.html            # Issue a ticket to an event
```

---

## User flows

### Registering as a user
1. Go to `/signup.html`
2. Enter email, password, and upload a government ID photo
3. The app reads your MRZ data and crops your face from the ID
4. Take a live selfie — it must match your ID photo to complete signup

### Logging in
1. Go to `/login.html`
2. Enter email and password
3. Users land on `/dashboard.html`, organizers land on `/organizer.html`

### Getting a ticket
1. From the dashboard, go to `/issue.html`
2. Enter an event code (given by the organizer)
3. A QR code ticket is generated and tied to your identity

### Organizer flow
1. Log in with an organizer account
2. Create events from the organizer dashboard
3. Share the event code with attendees
4. Use the face-scan feature at entry — the camera matches the live face against registered users and marks attendance automatically

---

## Adding an organizer account

Organizer accounts are not self-serve (by design — they require manual provisioning). Add one directly via the Python shell:

```bash
source .venv/bin/activate
cd backend
python3 -c "
import json, bcrypt
from pathlib import Path

email = 'you@example.com'
password = 'yourpassword'
name = 'Your Name'

path = Path('data/organizers.json')
data = json.loads(path.read_text())
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
data.append({'email': email, 'password': hashed, 'name': name})
path.write_text(json.dumps(data, indent=2))
print(f'Organizer {email} added.')
"
```

---

## Re-running setup / health check

You can re-run `setup.sh` at any time. It is safe to run multiple times — it skips steps that are already complete and reports the status of every required file and directory.

```bash
bash setup.sh
```

---

## Common issues

| Problem | Fix |
|---|---|
| `tesseract: command not found` | Run `bash setup.sh` — it installs tesseract |
| `MRZ not detected` on signup | Use a clearer, well-lit photo of the ID; MRZ must be fully visible |
| `No face detected` on signup | Ensure the ID photo has a clear front-facing portrait |
| `Live selfie does not match` | Better lighting, face the camera directly |
| Port 8000 already in use | Run `lsof -i :8000` to find the process and kill it, then restart |
| Missing JSON files on startup | Run `bash setup.sh` — it creates all missing data files |
