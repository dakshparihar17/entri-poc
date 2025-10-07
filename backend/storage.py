import json
from pathlib import Path

data_file = Path(__file__).parent / "tickets.json"
users_file = Path(__file__).parent / "users.json"


# Initialize file if not exists
for file in [data_file, users_file]:
    if not file.exists():
        with open(file, "w") as f:
            json.dump([], f)

# # Initialize file if not exists
# if not data_file.exists():
#     with open(data_file, "w") as f:
#         json.dump([], f)

def save_ticket(ticket_data: dict):
    with open(data_file, "r+") as f:
        data = json.load(f)
        data.append(ticket_data)
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=4)

def get_all_tickets():
    with open(data_file, "r") as f:
        return json.load(f)
    
def save_user(user_data: dict):
    with open(users_file, "r+") as f:
        data = json.load(f)
        data.append(user_data)
        f.seek(0)
        json.dump(data, f, indent=4)

def get_user_by_email(email: str):
    with open(users_file, "r") as f:
        users = json.load(f)
        for user in users:
            if user["email"] == email:
                return user
    return None

def get_tickets_by_email(email: str):
    """Return all tickets belonging to a specific user."""
    with open(data_file, "r") as f:
        tickets = json.load(f)
        return [t for t in tickets if t.get("email") == email]