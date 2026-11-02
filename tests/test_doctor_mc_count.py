"""MC count shown to doctors on teleconsult cards: last 30 days, MCs only, voided excluded.

Needs a real Postgres. Skipped unless TEST_POSTGRES_URL is set (see test_campaign_click_stats.py).
"""
import os
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_POSTGRES_URL not set")


def test_counts_only_the_patients_live_mcs_in_last_30_days():
    from models import Base
    from models.document import Document
    from models.model_enums import DocumentStatus, DocumentType
    from routers.doctor.actions.webhook import count_recent_mcs
    from utils import sg_datetime

    engine = create_engine(URL)
    Base.metadata.drop_all(engine, tables=[Document.__table__])
    Base.metadata.create_all(engine, tables=[Document.__table__])
    today = sg_datetime.now().date()

    with Session(engine) as db:
        def doc(patient, days_ago, type=DocumentType.MC, status=None):
            db.add(Document(
                sgimed_patient_id=patient, sgimed_document_id=str(uuid.uuid4()), sgimed_branch_id="b",
                name="x", document_date=today - timedelta(days=days_ago), document_type=type, status=status,
            ))

        doc("P1", 0); doc("P1", 29)                    # counted
        doc("P1", 30)                                  # outside the 30-day window
        doc("P1", 3, status=DocumentStatus.VOID)       # voided in SGiMed
        doc("P1", 3, type=DocumentType.INVOICE)        # not an MC
        doc("P2", 1)                                   # another patient
        db.commit()

        assert count_recent_mcs(db, "P1") == 2
        assert count_recent_mcs(db, "P2") == 1
        assert count_recent_mcs(db, None) == 0         # patient not yet linked to SGiMed
