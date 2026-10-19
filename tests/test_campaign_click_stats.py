"""Opened / ignored counts and recipient filters for marketing campaigns.

Needs a real Postgres (count DISTINCT ... FILTER). Skipped unless TEST_POSTGRES_URL is set, e.g.
  docker run -d --rm -p 55432:5432 -e POSTGRES_PASSWORD=pw postgres:16-alpine
  TEST_POSTGRES_URL=postgresql://postgres:pw@localhost:55432/postgres pytest tests/test_campaign_click_stats.py
"""
import os
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_POSTGRES_URL not set")


def test_opened_and_ignored_are_counted_per_patient(monkeypatch):
    from models import Base
    from models import model_enums as E
    from models.marketing_notifications import NotificationCampaign, NotificationCampaignRecipient as R
    from models.patient import Account
    from routers.admin import marketing_campaigns as admin
    from routers.patient import notification_preferences as prefs

    engine = create_engine(URL)
    tables = [Account.__table__, NotificationCampaign.__table__, R.__table__]
    Base.metadata.drop_all(engine, tables=tables)
    Base.metadata.create_all(engine, tables=tables)

    with Session(engine) as db:
        def patient(nric):
            acc = Account(
                ic_type=E.SGiMedICType.PINK_IC, nric=nric, name=nric, gender=E.SGiMedGender.MALE,
                date_of_birth=date(1990, 1, 1), nationality=E.SGiMedNationality.SINGAPORE_CITIZEN,
                language=E.SGiMedLanguage.ENGLISH, mobile_code=E.PhoneCountryCode.SINGAPORE, mobile_number="91234567",
            )
            db.add(acc)
            db.flush()
            return acc

        a, b, c, e = (patient(n) for n in ("S0000001A", "S0000002B", "S0000003C", "S0000005E"))
        camp = NotificationCampaign(id=uuid.uuid4(), type="marketing", title="t", body="b", total_recipients=6, sent_count=6)
        db.add(camp)
        db.flush()

        def device(acc, receipt):
            db.add(R(campaign_id=camp.id, account_id=acc.id, push_token=f"ExponentPushToken[{uuid.uuid4()}]",
                     status="sent", receipt_status=receipt))

        device(a, "ok"); device(a, "error")   # A: two phones, one delivered -> will tap
        device(b, "ok")                       # B: delivered, never taps     -> ignored
        device(c, None)                       # C: receipt still pending      -> neither
        device(e, "ok"); device(e, "ok")      # E: two phones delivered, no tap -> ignored once
        db.commit()

        # A taps twice: the real /opened endpoint stamps all of A's rows, first tap wins
        monkeypatch.setattr(prefs, "get_user", lambda db, uid: SimpleNamespace(id=a.id))
        prefs.campaign_opened(prefs.OpenedReq(campaign_id=camp.id), firebase_uid="x", db=db)
        first = {r.opened_at for r in db.query(R).filter(R.account_id == a.id)}
        prefs.campaign_opened(prefs.OpenedReq(campaign_id=camp.id), firebase_uid="x", db=db)
        db.expire_all()
        assert {r.opened_at for r in db.query(R).filter(R.account_id == a.id)} == first and None not in first

        row = admin._to_row(db, camp)
        assert (row.opened_count, row.ignored_count) == (1, 2)

        def listed(status):
            resp = admin.list_recipients(campaign_id=str(camp.id), status=status, limit=50, offset=0, db=db)
            return resp.total, sorted(r.nric for r in resp.rows)

        assert listed("opened") == (2, ["S0000001A", "S0000001A"])  # one row per device
        assert listed("ignored") == (3, ["S0000002B", "S0000005E", "S0000005E"])

        page2 = admin.list_recipients(campaign_id=str(camp.id), status=None, limit=4, offset=4, db=db)
        assert page2.total == 6 and len(page2.rows) == 2  # server-side paging

    Base.metadata.drop_all(engine, tables=tables)
