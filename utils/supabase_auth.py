import logging
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import SessionLocal
from models.model_enums import Role
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from config import supabase
from models.pinnacle import PinnacleAccount

class SupabaseUser(BaseModel):
    id: str
    supabase_uid: str
    role: Role

auth_scheme = HTTPBearer()
def get_current_user(token: HTTPAuthorizationCredentials) -> SupabaseUser:
    try:
        user = supabase.auth.get_user(token.credentials)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No User is found",
            )

        user = user.user
        with SessionLocal() as db:
            account = db.query(PinnacleAccount).filter(PinnacleAccount.supabase_uid == user.id).first()
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user",
                )

        return SupabaseUser(id=str(account.id), supabase_uid=user.id, role=account.role)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please relogin",
        )
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid. Please relogin",
        )
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error. Please relogin",
        )

def check_role(roles: list[Role], token: HTTPAuthorizationCredentials):
    user = get_current_user(token)
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Unauthorized access")
    return user

def get_superadmin(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    return check_role([Role.SUPERADMIN], token)
    
def get_admin(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    return check_role([Role.ADMIN], token)

def get_admin_or_superadmin(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    return check_role([Role.ADMIN, Role.SUPERADMIN], token)

def get_doctor_or_superadmin(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    return check_role([Role.DOCTOR, Role.ADMIN, Role.SUPERADMIN], token)

def get_logistic_or_superadmin(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    return check_role([Role.LOGISTIC, Role.ADMIN, Role.SUPERADMIN], token)

def get_dispatch_or_logistic_or_superadmin(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    return check_role([Role.DISPATCH, Role.LOGISTIC, Role.ADMIN, Role.SUPERADMIN], token)
