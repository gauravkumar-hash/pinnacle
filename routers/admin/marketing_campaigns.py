"""
Admin API for consent-notice / marketing broadcasts.

Mounted at /api/admin/marketing-campaigns (superadmin only).

Flow the admin panel drives:

  POST   /                      create a draft campaign (header, message, deep-link, type)
  GET    /                      list campaigns with live progress
  GET    /{id}                  one campaign + counters (sent / failed / skipped / pending)
  GET    /{id}/recipients       drill-down: per-user delivery status (paginated, filterable)
  POST   /{id}/prepare          build the audience (async) -> QUEUED
  POST   /{id}/start            begin sending -> SENDING (scheduler drains it in batches)
  POST   /{id}/pause            hold -> PAUSED
  POST   /{id}/resume           PAUSED -> SENDING
  DELETE /{id}                  delete a DRAFT campaign

Sending itself is done by the APScheduler worker in scheduler_actions/campaign_updates.py,
BATCH_SIZE devices per tick, so this API never blocks on a large send.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models import get_db
from models.marketing_notifications import (
    NotificationCampaign,
    NotificationCampaignRecipient,
    NotificationCampaignStatus,
    NotificationCampaignType,
)
from models.patient import Account
from scheduler_actions.campaign_updates import materialize_campaign_audience
from utils.fastapi import HTTPJSONException, SuccessResp
from utils.supabase_auth import get_superadmin

router = APIRouter(dependencies=[Depends(get_superadmin)])

_ALLOWED_CREATE_TYPES = {
    NotificationCampaignType.CONSENT_NOTICE.value,
    NotificationCampaignType.MARKETING.value,
    NotificationCampaignType.SYSTEM.value,
}


# --------------------------------------------------------------------------- schemas
class CampaignCreateReq(BaseModel):
    type: str = Field(description="consent_notice | marketing | system")
    title: str = Field(min_length=1, max_length=120, description="Notification header")
    body: str = Field(min_length=1, max_length=500, description="Notification message")
    # Deep-link payload delivered to the app on tap. Default opens the opt-out screen.
    data: Optional[dict] = Field(
        default={"pathname": "/profile/notification-settings"},
        description='e.g. {"pathname": "/profile/notification-settings"}',
    )


class CampaignRow(BaseModel):
    id: str
    type: str
    title: str
    body: str
    data: Optional[dict]
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    skipped_count: int
    pending_count: int
    delivered_count: int
    undelivered_count: int
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class CampaignListResp(BaseModel):
    rows: list[CampaignRow]


class RecipientRow(BaseModel):
    account_id: str
    name: Optional[str]
    mobile: Optional[str]
    status: str
    attempts: int
    last_error: Optional[str]
    sent_at: Optional[str]
    delivery: str  # delivered | undelivered | sent (accepted, receipt pending) | not_sent
    receipt_status: Optional[str]
    receipt_error: Optional[str]
    receipt_checked_at: Optional[str]


class RecipientListResp(BaseModel):
    total: int
    rows: list[RecipientRow]


# --------------------------------------------------------------------------- helpers
def _to_row(db: Session, c: NotificationCampaign) -> CampaignRow:
    pending = (
        c.total_recipients - c.sent_count - c.failed_count - c.skipped_count
    )
    return CampaignRow(
        id=str(c.id),
        type=c.type,
        title=c.title,
        body=c.body,
        data=c.data,
        status=c.status,
        total_recipients=c.total_recipients,
        sent_count=c.sent_count,
        failed_count=c.failed_count,
        skipped_count=c.skipped_count,
        pending_count=max(pending, 0),
        delivered_count=c.delivered_count or 0,
        undelivered_count=c.undelivered_count or 0,
        created_at=c.created_at.isoformat() if c.created_at else None,
        started_at=c.started_at.isoformat() if c.started_at else None,
        completed_at=c.completed_at.isoformat() if c.completed_at else None,
    )


def _get_or_404(db: Session, campaign_id: str) -> NotificationCampaign:
    c = db.get(NotificationCampaign, campaign_id)
    if c is None:
        raise HTTPJSONException(status_code=404, title="Not found", message="Campaign not found")
    return c


# --------------------------------------------------------------------------- routes
@router.post("", response_model=CampaignRow)
def create_campaign(req: CampaignCreateReq, db: Session = Depends(get_db)):
    if req.type not in _ALLOWED_CREATE_TYPES:
        raise HTTPJSONException(
            status_code=400, title="Bad request", message=f"Invalid type: {req.type}"
        )
    c = NotificationCampaign(
        type=req.type,
        title=req.title,
        body=req.body,
        data=req.data,
        status=NotificationCampaignStatus.DRAFT.value,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_row(db, c)


@router.get("", response_model=CampaignListResp)
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = (
        db.query(NotificationCampaign)
        .order_by(NotificationCampaign.created_at.desc())
        .all()
    )
    return CampaignListResp(rows=[_to_row(db, c) for c in campaigns])


@router.get("/{campaign_id}", response_model=CampaignRow)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    return _to_row(db, _get_or_404(db, campaign_id))


@router.get("/{campaign_id}/recipients", response_model=RecipientListResp)
def list_recipients(
    campaign_id: str,
    status: Optional[str] = Query(default=None, description="filter: pending|sent|failed|skipped|invalid_token"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _get_or_404(db, campaign_id)
    qry = (
        db.query(NotificationCampaignRecipient, Account)
        .outerjoin(Account, Account.id == NotificationCampaignRecipient.account_id)
        .filter(NotificationCampaignRecipient.campaign_id == campaign_id)
    )
    if status:
        qry = qry.filter(NotificationCampaignRecipient.status == status)
    total = qry.count()
    records = (
        qry.order_by(NotificationCampaignRecipient.id).offset(offset).limit(limit).all()
    )
    return RecipientListResp(
        total=total,
        rows=[_recipient_row(r, acc) for r, acc in records],
    )


def _recipient_row(r: NotificationCampaignRecipient, acc: Optional[Account]) -> RecipientRow:
    if r.receipt_status == "ok":
        delivery = "delivered"
    elif r.receipt_status == "error":
        delivery = "undelivered"
    elif r.status == "sent":
        delivery = "sent"  # Expo accepted it; delivery receipt not in yet
    else:
        delivery = "not_sent"
    mobile = None
    if acc is not None and acc.mobile_number:
        code = getattr(acc.mobile_code, "value", acc.mobile_code) or ""
        mobile = f"{code}{acc.mobile_number}".strip()
    return RecipientRow(
        account_id=str(r.account_id),
        name=acc.name if acc is not None else None,
        mobile=mobile,
        status=r.status,
        attempts=r.attempts,
        last_error=r.last_error,
        sent_at=r.sent_at.isoformat() if r.sent_at else None,
        delivery=delivery,
        receipt_status=r.receipt_status,
        receipt_error=r.receipt_error,
        receipt_checked_at=r.receipt_checked_at.isoformat() if r.receipt_checked_at else None,
    )


@router.post("/{campaign_id}/prepare", response_model=SuccessResp)
def prepare_campaign(
    campaign_id: str, background: BackgroundTasks, db: Session = Depends(get_db)
):
    c = _get_or_404(db, campaign_id)
    if c.status not in (
        NotificationCampaignStatus.DRAFT.value,
        NotificationCampaignStatus.QUEUED.value,
    ):
        raise HTTPJSONException(
            status_code=400,
            title="Bad state",
            message=f"Cannot prepare a campaign in state '{c.status}'",
        )
    # Rebuild from scratch so re-prepare is idempotent.
    db.query(NotificationCampaignRecipient).filter(
        NotificationCampaignRecipient.campaign_id == campaign_id
    ).delete(synchronize_session=False)
    db.commit()
    background.add_task(materialize_campaign_audience, str(c.id))
    return SuccessResp(success=True)


@router.post("/{campaign_id}/start", response_model=SuccessResp)
def start_campaign(campaign_id: str, db: Session = Depends(get_db)):
    from datetime import datetime

    c = _get_or_404(db, campaign_id)
    if c.status != NotificationCampaignStatus.QUEUED.value:
        raise HTTPJSONException(
            status_code=400,
            title="Bad state",
            message=f"Campaign must be 'queued' to start (is '{c.status}'). Run prepare first.",
        )
    c.status = NotificationCampaignStatus.SENDING.value
    if c.started_at is None:
        c.started_at = datetime.now()
    db.commit()
    return SuccessResp(success=True)


@router.post("/{campaign_id}/pause", response_model=SuccessResp)
def pause_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = _get_or_404(db, campaign_id)
    if c.status != NotificationCampaignStatus.SENDING.value:
        raise HTTPJSONException(
            status_code=400, title="Bad state", message="Only a sending campaign can be paused"
        )
    c.status = NotificationCampaignStatus.PAUSED.value
    db.commit()
    return SuccessResp(success=True)


@router.post("/{campaign_id}/resume", response_model=SuccessResp)
def resume_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = _get_or_404(db, campaign_id)
    if c.status != NotificationCampaignStatus.PAUSED.value:
        raise HTTPJSONException(
            status_code=400, title="Bad state", message="Only a paused campaign can be resumed"
        )
    c.status = NotificationCampaignStatus.SENDING.value
    db.commit()
    return SuccessResp(success=True)


@router.delete("/{campaign_id}", response_model=SuccessResp)
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = _get_or_404(db, campaign_id)
    if c.status != NotificationCampaignStatus.DRAFT.value:
        raise HTTPJSONException(
            status_code=400, title="Bad state", message="Only a draft campaign can be deleted"
        )
    db.delete(c)
    db.commit()
    return SuccessResp(success=True)
