"""
Patient-facing notification preferences.

Mounted at /api/notification-preferences

  GET   /                 current marketing opt-in state (lazily creates the row)
  PATCH /                 patient flips the toggle in the in-app settings screen
  POST  /unsubscribe      public, token-based opt-out for the web link in an SMS/email notice
                          (not used for push-only consent notices)

The in-app "Marketing & health-info notifications" screen calls GET then PATCH.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db, get_user
from models.marketing_notifications import (
    MarketingOptOutSource,
    PatientNotificationPreference,
)
from routers.patient.utils import validate_firebase_token
from utils.fastapi import HTTPJSONException, SuccessResp
from utils.unsubscribe_token import verify_unsubscribe_token

router = APIRouter()


class PreferenceResp(BaseModel):
    marketing_opt_in: bool


class PreferenceUpdateReq(BaseModel):
    marketing_opt_in: bool


class UnsubscribeReq(BaseModel):
    token: str


def _get_or_create(db: Session, account_id) -> PatientNotificationPreference:
    pref = db.get(PatientNotificationPreference, account_id)
    if pref is None:
        pref = PatientNotificationPreference(account_id=account_id, marketing_opt_in=True)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def _apply(pref: PatientNotificationPreference, opt_in: bool, source: str) -> None:
    pref.marketing_opt_in = opt_in
    if opt_in:
        pref.opted_out_at = None
        pref.opt_out_source = None
    else:
        pref.opted_out_at = datetime.now()
        pref.opt_out_source = source


@router.get("", response_model=PreferenceResp)
def get_preferences(
    firebase_uid: str = Depends(validate_firebase_token), db: Session = Depends(get_db)
):
    user = get_user(db, firebase_uid)
    if not user:
        raise HTTPJSONException(status_code=403, title="Forbidden", message="Invalid user")
    pref = _get_or_create(db, user.id)
    return PreferenceResp(marketing_opt_in=pref.marketing_opt_in)


@router.patch("", response_model=PreferenceResp)
def update_preferences(
    req: PreferenceUpdateReq,
    firebase_uid: str = Depends(validate_firebase_token),
    db: Session = Depends(get_db),
):
    user = get_user(db, firebase_uid)
    if not user:
        raise HTTPJSONException(status_code=403, title="Forbidden", message="Invalid user")
    pref = _get_or_create(db, user.id)
    _apply(pref, req.marketing_opt_in, MarketingOptOutSource.APP_SETTINGS.value)
    db.commit()
    return PreferenceResp(marketing_opt_in=pref.marketing_opt_in)


@router.post("/unsubscribe", response_model=SuccessResp)
def unsubscribe_via_link(req: UnsubscribeReq, db: Session = Depends(get_db)):
    """Public. Opt-out only - a valid token can never re-subscribe."""
    account_id = verify_unsubscribe_token(req.token)
    if not account_id:
        raise HTTPJSONException(
            status_code=400, title="Invalid link", message="This unsubscribe link is not valid."
        )
    pref = _get_or_create(db, account_id)
    _apply(pref, False, MarketingOptOutSource.MASS_NOTICE_LINK.value)
    db.commit()
    return SuccessResp(success=True)
