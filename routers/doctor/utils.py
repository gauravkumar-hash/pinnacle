from fastapi import Header, HTTPException, status
from typing import Dict, Optional
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from config import supabase
from supabase import Client
from asyncio import Queue
from sqlalchemy.orm import Session

async def get_current_user(authorization: str = Header(...)) -> Dict:
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )

        token = authorization.split(" ")[1]
        user = supabase.auth.get_user(token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No User is found",
            )

        user = user.user
        return {"user_id": user.id}
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid",
        )

class SessionManager:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.queues: dict[str, Queue] = {}
        self.branch_identifier: dict[str, str] = {}

    async def get_or_create_session(self, user_id: str, branch_id: Optional[str] = None):
        self.queues[user_id] = Queue()
        
        if branch_id != None: 
            self.branch_identifier[user_id] = branch_id
            print("Adding branch_id")
        
        return self.queues[user_id]

    def update_session(self, user_id: str, message):
        queue = self.queues[user_id]
        queue.put_nowait(message)

    def update_all_sessions(self, message):
        for id, queue in self.queues.items():
            print("Inserting new message")
            print(queue)
            queue.put_nowait(message)
            print("Message inserted")
            
    def update_all_sessions_using_branch_id(self, message, branch_id: str, db: Session):
        for id, queue in self.queues.items():
            print("Checking branch id")
            print(id)
            print(str(self.branch_identifier[id]) == str(branch_id))
            print(self.branch_identifier[id])
            print(branch_id)
            
            if str(self.branch_identifier[id]) == str(branch_id):
                print("Sending to specific place")
                queue.put_nowait(message)
                print("Message inserted")
            
    def delete_client(self, user_id: str):
        if user_id not in self.queues:
            print("Error: Doctor not found in clients")
            return
        
        print("Deleting Current Session")
        del self.queues[user_id]
session_manager = SessionManager(supabase)