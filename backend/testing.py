
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from blockchain import Blockchain
import hashlib
import os
from storage import save_ticket
from pathlib import Path

app = FastAPI()

# Paths
frontend_path = Path(__file__).parent.parent / "frontend"
tickets_path = Path(__file__).parent / "tickets"
tickets_path.mkdir(exist_ok=True)  # Ensure tickets folder exists

# Serve frontend files
@app.get("/")
def read_index():
    return FileResponse(frontend_path / "index.html")

@app.get("/issue.html")
def issue_ticket_page():
    return FileResponse(frontend_path / "issue.html")

# Serve static files
app.mount("/static", StaticFiles(directory=frontend_path), name="static")
app.mount("/tickets", StaticFiles(directory=tickets_path), name="tickets")

blockchain = Blockchain()

# Data model
class TicketRequest(BaseModel):
    user_email: str
    ticket_id: str  # Changed name for clarity

@app.post("/issue.html")
def issue_ticket(data: TicketRequest):
    # Add block with email + ticket_id
    block = blockchain.add_block({"email": data.user_email, "ticket_id": data.ticket_id})

    return {
        "block_index": block.index,
        "transaction_hash": block.hash,
        "previous_hash": block.previous_hash
    }
    save_ticket(data.user_email, data.event_id, ticket_id, block.hash)


# # Ticket data model
# class TicketRequest(BaseModel):
#     user_email: str
#     event_id: str

# # Issue ticket endpoint
# @app.post("/verify.html")
# def issue_ticket(data: TicketRequest):
#     ticket_id_raw = f"{data.user_email}-{data.event_id}"
#     ticket_id = hashlib.sha256(ticket_id_raw.encode()).hexdigest()

#     # Generate QR code
#     qr = qrcode.make(ticket_id)
#     qr_path = tickets_path / f"{ticket_id}.png"
#     qr.save(qr_path)

#     return {
#         "ticket_id": ticket_id,
#         "qr_code_url": f"/tickets/{ticket_id}.png"
#     }
 