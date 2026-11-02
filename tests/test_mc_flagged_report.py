"""Super admin "MC flagged cases" report: teleconsults where the patient had MCs in the 30 days up to the visit.

Needs a real Postgres. Skipped unless TEST_POSTGRES_URL is set (see test_campaign_click_stats.py).
"""
import asyncio
import io
import os
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_POSTGRES_URL not set")


def test_mc_flagged_report_rows_and_excel():
    from models import Base
    from models.document import Document
    from models.patient import Account
    from models.pinnacle import Branch, PinnacleAccount
    from models.teleconsult import Teleconsult

    engine = create_engine(URL)
    tables = [Branch.__table__, PinnacleAccount.__table__, Account.__table__, Teleconsult.__table__, Document.__table__]
    Base.metadata.drop_all(engine, tables=tables)
    Base.metadata.create_all(engine, tables=tables)
    try:
        _check_report(engine)
    finally:
        Base.metadata.drop_all(engine, tables=tables)  # shared test DB: leave nothing behind


def _check_report(engine):
    from fastapi import HTTPException
    from openpyxl import load_workbook
    from models import model_enums as E
    from models.document import Document
    from models.patient import Account
    from models.pinnacle import PinnacleAccount
    from models.teleconsult import Teleconsult
    from routers.admin import reports

    with Session(engine) as db:
        doctor = PinnacleAccount(supabase_uid="u1", name="Dr Lim", email="lim@x.sg", role=E.Role.DOCTOR)
        db.add(doctor)

        def patient(nric, sgimed_id):
            acc = Account(
                ic_type=E.SGiMedICType.PINK_IC, nric=nric, name=f"Patient {nric}", gender=E.SGiMedGender.MALE,
                date_of_birth=date(1990, 1, 1), nationality=E.SGiMedNationality.SINGAPORE_CITIZEN,
                language=E.SGiMedLanguage.ENGLISH, mobile_code=E.PhoneCountryCode.SINGAPORE, mobile_number="91234567",
                sgimed_patient_id=sgimed_id,
            )
            db.add(acc)
            db.flush()
            return acc

        a, b, c, d, e = (patient(n, s) for n, s in [
            ("S0000001A", "PA"), ("S0000002B", "PB"), ("S0000003C", "PC"), ("S0000004D", "PD"), ("S0000005E", None)])

        def visit(acc, checkin_utc, visit_id, patient_type=E.PatientType.PRIVATE_PATIENT, with_doctor=True):
            db.add(Teleconsult(
                account_id=acc.id, patient_type=patient_type, address="x", payment_breakdown=[], total=0,
                status=E.TeleconsultStatus.CHECKED_OUT, sgimed_visit_id=visit_id, checkin_time=checkin_utc,
                doctor_id=doctor.id if with_doctor else None,
            ))

        def mc(sgimed_id, on, visit_id=None, status=None):
            db.add(Document(
                sgimed_patient_id=sgimed_id, sgimed_document_id=str(uuid.uuid4()), sgimed_branch_id="b",
                sgimed_visit_id=visit_id, name="MC", document_date=on, document_type=E.DocumentType.MC, status=status,
            ))

        db.flush()
        # A (PT): 14 Oct 17:00 UTC = 15 Oct 01:00 SGT -> visit date 15 Oct
        visit(a, datetime(2026, 10, 14, 17, 0), "VA1")
        mc("PA", date(2026, 10, 1))                                      # in window -> counted
        mc("PA", date(2026, 9, 10))                                      # 35 days before -> not counted
        mc("PA", date(2026, 10, 10), status=E.DocumentStatus.VOID)       # voided -> not counted
        mc("PA", date(2026, 10, 15), visit_id="VA1")                     # this visit's MC -> not counted, mc_given
        visit(a, datetime(2026, 10, 18, 2, 0), "VA2", with_doctor=False)  # no doctor assigned -> not a visit
        # B (MW): visit 20 Oct, MCs 29 days and 1 day before, none for this visit
        visit(b, datetime(2026, 10, 20, 2, 0), "VB1", patient_type=E.PatientType.MIGRANT_WORKER)
        mc("PB", date(2026, 9, 21))
        mc("PB", date(2026, 10, 19))
        mc("PB", date(2026, 9, 20))                                      # exactly 30 days before -> outside window
        # C: MC only for this visit -> not flagged
        visit(c, datetime(2026, 10, 16, 2, 0), "VC1")
        mc("PC", date(2026, 10, 16), visit_id="VC1")
        # D: has prior MCs but visit is after the range
        visit(d, datetime(2026, 11, 5, 2, 0), "VD1")
        mc("PD", date(2026, 11, 1))
        # E: not linked to SGiMed
        visit(e, datetime(2026, 10, 17, 2, 0), "VE1")
        db.commit()

        rows = reports.get_mc_flagged_rows(db, date(2026, 10, 15), date(2026, 10, 31))
        assert [(r.visit_date, r.patient_nric, r.branch, r.doctor_name, r.mc_count_30d, r.mc_given) for r in rows] == [
            (date(2026, 10, 15), "S0000001A", "PT", "Dr Lim", 1, True),
            (date(2026, 10, 20), "S0000002B", "MW", "Dr Lim", 2, False),
        ]

        # Range validation at the API boundary
        for start, end in [(date(2026, 10, 31), date(2026, 10, 1)), (date(2025, 1, 1), date(2026, 1, 2))]:  # end before start; 367 days
            with pytest.raises(HTTPException) as err:
                reports.get_mc_flagged_rows(db, start, end)
            assert err.value.status_code == 400

        # Excel export: header row + one row per flagged case, visit date stored as a real date
        resp = reports.export_mc_flagged_report(date(2026, 10, 15), date(2026, 10, 31), db)

        async def read():
            return b"".join([chunk async for chunk in resp.body_iterator])

        ws = load_workbook(io.BytesIO(asyncio.run(read()))).active
        values = list(ws.iter_rows(values_only=True))
        assert values[0] == ("Visit Date", "Patient NRIC", "Patient Name", "Branch (MW/PT)", "Doctor Assigned",
                             "No. of MC (30 days before visit)", "MC Given on Visit")
        assert values[1][0].date() == date(2026, 10, 15)
        assert values[1][1:] == ("S0000001A", "Patient S0000001A", "PT", "Dr Lim", 1, "Yes")
        assert values[2][1:] == ("S0000002B", "Patient S0000002B", "MW", "Dr Lim", 2, "No")
        assert len(values) == 3
        assert "mc_flagged_report_2026-10-15_2026-10-31.xlsx" in resp.headers["content-disposition"]
