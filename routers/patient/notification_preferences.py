"""
Patient-facing notification preferences.

Mounted at /api/notification-preferences

  GET   /                 current preference state (lazily creates the row)
  PATCH /                 patient flips either toggle in the in-app settings screen

Two independent switches:
  enable_notifications -> master. false = send nothing at all (appointment, health, marketing).
  marketing_opt_in     -> narrow. false = no marketing / health-info blasts, everything else
                          still sends.
  POST  /unsubscribe      public, token-based opt-out for the web link in an SMS/email notice
                          (not used for push-only consent notices)
  POST  /opened           app reports the patient tapped a campaign notification (click tracking)

The in-app "Marketing & health-info notifications" screen calls GET then PATCH.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db, get_user
from models.marketing_notifications import (
    MarketingOptOutSource,
    NotificationCampaignRecipient,
    PatientNotificationPreference,
)
from routers.patient.utils import validate_firebase_token
from utils.fastapi import HTTPJSONException, SuccessResp
from utils.unsubscribe_token import verify_unsubscribe_token

router = APIRouter()
logger = logging.getLogger("notification_preferences")


class PreferenceResp(BaseModel):
    enable_notifications: bool
    marketing_opt_in: bool


class PreferenceUpdateReq(BaseModel):
    # Both optional so the app can PATCH one toggle without clobbering the other.
    enable_notifications: Optional[bool] = None
    marketing_opt_in: Optional[bool] = None


class UnsubscribeReq(BaseModel):
    token: str


class OpenedReq(BaseModel):
    campaign_id: uuid.UUID


def _get_or_create(db: Session, account_id) -> PatientNotificationPreference:
    pref = db.get(PatientNotificationPreference, account_id)
    if pref is None:
        pref = PatientNotificationPreference(account_id=account_id, marketing_opt_in=True)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


def _apply(pref: PatientNotificationPreference, opt_in: bool, source: str) -> None:
    """Set the marketing flag and keep the opt-out audit trail in step."""
    pref.marketing_opt_in = opt_in
    if opt_in:
        pref.opted_out_at = None
        pref.opt_out_source = None
    else:
        pref.opted_out_at = datetime.now()
        pref.opt_out_source = source


def _to_resp(pref: PatientNotificationPreference) -> "PreferenceResp":
    return PreferenceResp(
        enable_notifications=pref.enable_notifications,
        marketing_opt_in=pref.marketing_opt_in,
    )


@router.get("", response_model=PreferenceResp)
def get_preferences(
    firebase_uid: str = Depends(validate_firebase_token), db: Session = Depends(get_db)
):
    user = get_user(db, firebase_uid)
    if not user:
        raise HTTPJSONException(status_code=403, title="Forbidden", message="Invalid user")
    pref = _get_or_create(db, user.id)
    return _to_resp(pref)


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
    if req.enable_notifications is not None:
        pref.enable_notifications = req.enable_notifications
    if req.marketing_opt_in is not None:
        _apply(pref, req.marketing_opt_in, MarketingOptOutSource.APP_SETTINGS.value)
    db.commit()
    return _to_resp(pref)


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


@router.post("/opened", response_model=SuccessResp)
def campaign_opened(
    req: OpenedReq,
    firebase_uid: str = Depends(validate_firebase_token),
    db: Session = Depends(get_db),
):
    """Record that the patient tapped a campaign notification. Only the first tap counts."""
    user = get_user(db, firebase_uid)
    if not user:
        logger.warning("Campaign %s opened: no account for firebase_uid %s", req.campaign_id, firebase_uid)
        raise HTTPJSONException(status_code=403, title="Forbidden", message="Invalid user")
    stamped = db.query(NotificationCampaignRecipient).filter(
        NotificationCampaignRecipient.campaign_id == req.campaign_id,
        NotificationCampaignRecipient.account_id == user.id,
        NotificationCampaignRecipient.opened_at.is_(None),
    ).update({NotificationCampaignRecipient.opened_at: datetime.now()}, synchronize_session=False)
    db.commit()
    # stamped=0 is normal for a repeat tap; on a first tap it means this account was not a recipient
    logger.info("Campaign %s opened by account %s: %s row(s) stamped", req.campaign_id, user.id, stamped)
    return SuccessResp(success=True)
