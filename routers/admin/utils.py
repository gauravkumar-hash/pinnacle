from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, PyJWTError, InvalidTokenError
from config import supabase
import logging

auth_scheme = HTTPBearer()
logger = logging.getLogger(__name__)

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    """
    Validate the JWT token from the Authorization header.
    Returns user info if valid, raises 401 if expired or invalid.
    """
    try:
        if not token or not token.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided",
            )
        
        user = supabase.auth.get_user(token.credentials)
        if user is None:
            logger.warning("Supabase returned None for user - token may be invalid or expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid or has expired. Please log in again.",
            )

        # TODO: Check the user metadata to determine if the user is an admin or doctor

        user_obj = user.user
        return {"user_id": user_obj.id}
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except ExpiredSignatureError:
        logger.warning(f"Token has expired for token: {token.credentials[:20]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
        )
    except (PyJWTError, InvalidTokenError) as e:
        logger.warning(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid. Please log in again.",
        )
    except Exception as e:
        logger.error(f"Unexpected error in token validation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Please log in again.",
        )
