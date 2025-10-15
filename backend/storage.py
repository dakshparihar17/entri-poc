import json
from pathlib import Path

data_file = Path(__file__).parent / "tickets.json"
users_file = Path(__file__).parent / "users.json"
data_dir = Path(__file__).parent / "data"



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
    

def load_json(filename: str):
    """Load JSON data from a file. Returns an empty list if the file doesn't exist."""
    file_path = Path(__file__).parent / filename
    if not file_path.exists():
        return []
    with open(file_path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_json(filename: str, data):
    """Overwrite a JSON file with new data."""
    file_path = Path(__file__).parent / filename
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)