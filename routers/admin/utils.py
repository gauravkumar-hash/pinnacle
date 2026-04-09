from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from config import supabase

auth_scheme = HTTPBearer()
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    try:
        
        user = supabase.auth.get_user(token.credentials)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No User is found",
            )

        # TODO: Check the user metadata to determine if the user is an admin or doctor

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
