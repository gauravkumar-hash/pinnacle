"""MC count shown to doctors on teleconsult cards: last 30 days, MCs only, voided excluded.

Needs a real Postgres. Skipped unless TEST_POSTGRES_URL is set (see test_campaign_click_stats.py).
"""
import os
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text
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

    # Query error (here: table gone) -> None, and the caller's session keeps working
    Base.metadata.drop_all(engine, tables=[Document.__table__])
    with Session(engine) as db:
        assert count_recent_mcs(db, "P1") is None
        assert db.execute(text("select 1")).scalar() == 1


def test_telemed_count_only_includes_mcs_from_the_patients_other_teleconsults():
    from datetime import datetime
    from models import Base
    from models import model_enums as E
    from models.document import Document
    from models.patient import Account
    from models.pinnacle import Branch, PinnacleAccount
    from models.teleconsult import Teleconsult
    from routers.doctor.actions.webhook import count_recent_mcs
    from utils import sg_datetime

    engine = create_engine(URL)
    tables = [Branch.__table__, PinnacleAccount.__table__, Account.__table__, Teleconsult.__table__, Document.__table__]
    Base.metadata.drop_all(engine, tables=tables)
    Base.metadata.create_all(engine, tables=tables)
    today = sg_datetime.now().date()
    try:
        with Session(engine) as db:
            def patient(nric, sgimed_id):
                acc = Account(
                    ic_type=E.SGiMedICType.PINK_IC, nric=nric, name=nric, gender=E.SGiMedGender.MALE,
                    date_of_birth=datetime(1990, 1, 1).date(), nationality=E.SGiMedNationality.SINGAPORE_CITIZEN,
                    language=E.SGiMedLanguage.ENGLISH, mobile_code=E.PhoneCountryCode.SINGAPORE, mobile_number="91234567",
                    sgimed_patient_id=sgimed_id,
                )
                db.add(acc)
                db.flush()
                return acc

            def teleconsult(acc, visit_id, patient_type=E.PatientType.PRIVATE_PATIENT):
                t = Teleconsult(
                    account_id=acc.id, patient_type=patient_type, address="x", payment_breakdown=[], total=0,
                    status=E.TeleconsultStatus.CHECKED_OUT, sgimed_visit_id=visit_id,
                )
                db.add(t)
                db.flush()
                return t

            def mc(sgimed_id, days_ago, visit_id, status=None):
                db.add(Document(
                    sgimed_patient_id=sgimed_id, sgimed_document_id=str(uuid.uuid4()), sgimed_branch_id="b",
                    sgimed_visit_id=visit_id, name="MC", document_date=today - timedelta(days=days_ago),
                    document_type=E.DocumentType.MC, status=status,
                ))

            a, b = patient("S0000001A", "PA"), patient("S0000002B", "PB")
            current = teleconsult(a, "V0")
            teleconsult(a, "V1"); teleconsult(a, "V2", E.PatientType.MIGRANT_WORKER); teleconsult(a, "V3"); teleconsult(a, None)
            teleconsult(b, "VB")
            mc("PA", 5, "V1")                                   # earlier PT teleconsult -> counted
            mc("PA", 20, "V2")                                  # earlier MW teleconsult -> counted
            mc("PA", 6, "V1", status=E.DocumentStatus.VOID)     # voided -> not counted
            mc("PA", 40, "V3")                                  # outside 30 days -> not counted
            mc("PA", 3, "W1")                                   # walk-in clinic visit -> not counted
            mc("PA", 2, None)                                   # no visit -> not counted
            mc("PA", 0, "V0")                                   # this consult's own MC -> not counted
            mc("PB", 1, "VB")                                   # another patient
            db.commit()

            assert count_recent_mcs(db, "PA", telemed_of=current) == 2
            assert count_recent_mcs(db, "PA") == 5              # all-MC chip unchanged: V1, V2, W1, no-visit, V0
            assert count_recent_mcs(db, "PB", telemed_of=current) == 0  # PB's MCs are not on A's teleconsults
            assert count_recent_mcs(db, None, telemed_of=current) == 0
    finally:
        Base.metadata.drop_all(engine, tables=tables)
