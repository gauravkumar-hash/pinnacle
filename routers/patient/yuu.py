from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db, Account, AccountYuuLink
from routers.patient.utils import validate_user
from utils.integrations.yuu_client import yuu_client
from utils.fastapi import HTTPJSONException, ExceptionCode
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yuu", dependencies=[Depends(validate_user)])

class YuuStatusResponse(BaseModel):
    is_linked: bool
    tomo_id: Optional[str] = None
    linked_at: Optional[datetime] = None

class YuuWebpageResponse(BaseModel):
    redirect_url: str

class YuuLinkRequest(BaseModel):
    code: str
    state: str

class YuuSuccessResponse(BaseModel):
    show_success_modal: bool

@router.get("", response_model=YuuStatusResponse)
def get_yuu_status(user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    """Get current Yuu link status for the user"""
    if user.yuu_link:
        return YuuStatusResponse(
            is_linked=True,
            tomo_id=user.yuu_link.tomo_id,
            linked_at=user.yuu_link.linked_at
        )
    
    return YuuStatusResponse(is_linked=False)

@router.get("/webpage", response_model=YuuWebpageResponse)
def get_yuu_webpage(user: Account = Depends(validate_user)):
    """Get Yuu OAuth webpage URL for in-app browser
    
    User Flow:
    1. User clicks "Link Account" button
    2. App calls this endpoint to get Yuu webpage URL
    3. App opens in-app browser with the URL
    4. User logs in to Yuu and authorizes
    5. Yuu redirects to pinnaclesgplus://profile/yuu?code=XXX&state=YYY
    """
    # Check if already linked
    if user.yuu_link:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.YUU_ALREADY_LINKED,
            title="Already Linked",
            message="Your account is already linked to Yuu."
        )
    
    # Generate state for CSRF protection
    # State is passed to Yuu and will be returned in the callback
    state = str(user.id)  # Use user ID as state for simplicity
    
    # Get OAuth URL from Yuu
    try:
        redirect_url = yuu_client.get_preauth_url(state)
    except Exception as e:
        logger.error(f"Yuu preauth failed: {str(e)}")
        raise HTTPJSONException(
            status_code=500,
            code=ExceptionCode.YUU_API_ERROR,
            title="Yuu Service Error",
            message="Unable to connect to Yuu service. Please try again later."
        )
    
    return YuuWebpageResponse(redirect_url=redirect_url)

# Used to prevent duplicate requests.
yuu_state_code_cache_size = 10
yuu_state_code_cache = []

def check_yuu_state_code_cache(state: str, code: str) -> bool:
    global yuu_state_code_cache
    return f"{state}_{code}" in yuu_state_code_cache

def add_to_yuu_state_code_cache(state: str, code: str):
    global yuu_state_code_cache
    yuu_state_code_cache.append(f"{state}_{code}")
    yuu_state_code_cache = yuu_state_code_cache[-yuu_state_code_cache_size:]

@router.post("/link", response_model=YuuSuccessResponse)
def yuu_link_account(request: YuuLinkRequest, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    global yuu_state_code_cache
    """Complete Yuu account linking after OAuth callback
    
    Flow:
    1. App listens for redirect: pinnaclesgplus://app/profile/yuu?code=XXX&state=YYY
    2. App extracts code and state from URL
    3. App calls this endpoint with code and state
    4. Backend exchanges code for tokens and links account
    """
    # If user is already linked or request is a duplicate, ignore the request
    if user.yuu_link or check_yuu_state_code_cache(request.state, request.code):
        return YuuSuccessResponse(
            show_success_modal=False,
        )

    # Exchange code for tokens
    try:
        token_response = yuu_client.exchange_code_for_token(request.code)
    except Exception as e:
        logger.error(f"Token exchange failed: {str(e)}")
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID_YUU_CODE,
            title="Invalid Authorization",
            message="The authorization code is invalid or expired."
        )
    
    # Decrypt ID token to get user info
    try:
        yuu_user = yuu_client.decrypt_and_link(token_response['id_token'])
    except Exception as e:
        logger.error(f"Token decryption failed: {str(e)}")
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID_YUU_TOKEN,
            title="Invalid Token",
            message="Unable to process Yuu account information."
        )
    
    # Check if Yuu ID already linked to another account
    another_link = db.query(AccountYuuLink).filter(
        AccountYuuLink.deleted == False,
        AccountYuuLink.tomo_id == yuu_user['tomo_id'],
        AccountYuuLink.account_id != user.id
    ).first()

    if another_link:
        add_to_yuu_state_code_cache(request.state, request.code)
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.YUU_ID_IN_USE,
            title="Yuu Account In Use",
            message="This Yuu account is already linked to another Pinnacle account."
        )
    
    # Link accounts in Yuu system
    try:
        success = yuu_client.link_account(
            yuu_user['tomo_id'],
            yuu_user['user_identifier']
        )
        
        if not success:
            raise HTTPJSONException(
                status_code=500,
                code=ExceptionCode.YUU_LINK_FAILED,
                title="Linking Failed",
                message="Unable to complete account linking. Please try again."
            )
    except HTTPJSONException:
        raise
    except Exception as e:
        logger.error(f"Account linking failed: {str(e)}")
        raise HTTPJSONException(
            status_code=500,
            code=ExceptionCode.YUU_LINK_FAILED,
            title="Linking Failed",
            message="Unable to link your Yuu account. Please try again."
        )

    existing_link = db.query(AccountYuuLink).filter(AccountYuuLink.account_id == user.id).first()
    # Save to database
    if existing_link:
        # Reactivate existing link
        existing_link.deleted = False
        existing_link.deleted_at = None
        existing_link.tomo_id = yuu_user['tomo_id']
        existing_link.user_identifier = yuu_user['user_identifier']
        existing_link.linked_at = datetime.now()
    else:
        # Create new link
        yuu_link = AccountYuuLink(
            account_id=user.id,
            tomo_id=yuu_user['tomo_id'],
            user_identifier=yuu_user['user_identifier']
        )
        db.add(yuu_link)
    
    db.commit()
    add_to_yuu_state_code_cache(request.state, request.code)

    return YuuSuccessResponse(
        show_success_modal=True,
    )

@router.post("/unlink", response_model=YuuSuccessResponse)
def yuu_unlink_account(user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    """Unlink Yuu account from Pinnacle"""
    
    if not user.yuu_link:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.YUU_NOT_LINKED,
            title="Not Linked",
            message="Your account is not linked to Yuu."
        )
    
    # Unlink in Yuu system
    try:
        success = yuu_client.unlink_account(
            user.yuu_link.tomo_id,
            user.yuu_link.user_identifier
        )
        
        if not success:
            raise HTTPJSONException(
                status_code=500,
                code=ExceptionCode.YUU_UNLINK_FAILED,
                title="Unlinking Failed",
                message="Unable to unlink your account. Please try again."
            )
    except HTTPJSONException:
        raise
    except Exception as e:
        logger.error(f"Account unlinking failed: {str(e)}")
        raise HTTPJSONException(
            status_code=500,
            code=ExceptionCode.YUU_UNLINK_FAILED,
            title="Unlinking Failed",
            message="Unable to unlink your Yuu account. Please try again."
        )
    
    # Soft delete in database
    user.yuu_link.deleted = True
    user.yuu_link.deleted_at = datetime.now()
    db.commit()
    
    return YuuSuccessResponse(show_success_modal=True)

@router.get("/verify", response_model=Dict[str, Any])
def verify_yuu_membership(user: Account = Depends(validate_user)):
    """Verify active Yuu membership status"""
    if not user.yuu_link:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.YUU_NOT_LINKED,
            title="Not Linked",
            message="Your account is not linked to Yuu."
        )
    
    # Verify with Yuu API
    membership_data = yuu_client.verify_membership(
        user.yuu_link.tomo_id,
        user.yuu_link.user_identifier
    )
    
    if not membership_data:
        return {"active": False, "message": "Unable to verify membership status"}
    
    return membership_data