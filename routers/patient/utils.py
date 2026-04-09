import asyncio
import logging
import uuid
from fastapi import Depends, HTTPException
from firebase_admin import auth
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import sentry_sdk
from sqlalchemy.orm import Session
from models import Account, get_db, get_user

auth_scheme = HTTPBearer()
def validate_firebase_token(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    try:
        decoded_token = auth.verify_id_token(token.credentials)
        return decoded_token['uid']
    except Exception as e:
        logging.error(f"Error validating token: {e}")
        raise HTTPException(status_code=403, detail="Invalid token")

def validate_user(db: Session = Depends(get_db), firebase_uid: str = Depends(validate_firebase_token)) -> Account:
    user = get_user(db, firebase_uid)
    if not user:
        logging.error(f"Firebase UID not found in AccountFirebase: {firebase_uid}")
        raise HTTPException(status_code=403, detail="Invalid user")
    sentry_sdk.set_user({ "id": str(user.id), "name": user.name })
    return user
# def add_error_response(router: APIRouter):
#     def decorator(func):
#         if "responses" not in func.__dict__:
#             func.__dict__["responses"] = {}
#         func.__dict__["responses"][400] = {
#             "model": ErrorResponse, 
#             "description": "Exception triggered on backend server"
#         }
#         return func
#     return decorator

# SessionManager for Supabase Webhook
class SessionManager:
    def __init__(self):
        self.clients = {}
        
    def add_client(self, user_id):
        # Generate a Random Unique ID
        session_id = str(uuid.uuid4())
        if user_id not in self.clients:
            self.clients[user_id] = {}
            
        queue = asyncio.Queue()
        self.clients[user_id][session_id] = queue
        return session_id, queue

    def delete_client(self, user_id, session_id):
        if user_id not in self.clients:
            print("Error: User not found in clients")
            return
        if session_id not in self.clients[user_id]:
            print("Error: Session not found in clients")
            return

        if len(self.clients[user_id].keys()) == 1:
            print("Deleting Entire Record")
            del self.clients[user_id]
        else:
            print("Deleting Only One Session")
            del self.clients[user_id][session_id]

    def send_message(self, user_id, message):
        print(f"Sending Message to {user_id}")
        if user_id in self.clients:
            print(f"Sending to {len(self.clients[user_id].keys())} clients")
            for queue in self.clients[user_id].values():
                queue.put_nowait(message)
        else:
            print(f"Client {user_id} not found")

session_manager = SessionManager()
