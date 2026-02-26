from datetime import date, datetime, timedelta
from io import StringIO
import csv
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import get_db, Account, HealthReport, HealthReportProfile, IncomingReport, Measurement
from utils.supabase_auth import get_superadmin
from utils import sg_datetime
from repository.health_report.mapping import health_report_profiles
from services.health_report import generate_health_report_pdf
from scheduler_actions.sgimed_health_report_updates import generate_health_reports, _update_measurements_cron
from config import supabase
from utils.integrations.sgimed import get

router = APIRouter(dependencies=[Depends(get_superadmin)])

class HealthReportResponse(BaseModel):
    sgimed_hl7_id: str
    sgimed_patient_id: str
    sgimed_report_id: str
    sgimed_report_file_date: datetime
    patient_nric: Optional[str]
    patient_name: Optional[str]
    disclaimer_accepted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class HealthReportListResponse(BaseModel):
    data: List[HealthReportResponse]
    total: int
    page: int
    limit: int

class HealthReportListRequest(BaseModel):
    start_date: date
    end_date: date
    nrics: Optional[str] = None  # Comma-separated NRICs (e.g., "SxxxA,SxxxB")

@router.post("/list", response_model=HealthReportListResponse)
async def get_health_reports(
    request: HealthReportListRequest,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get health reports with optional filtering by NRICs and date range"""

    # Calculate offset
    offset = (page - 1) * limit

    # Date range (in UTC)
    start_datetime = sg_datetime.midnight(request.start_date)
    end_datetime = sg_datetime.midnight(request.end_date) + timedelta(days=1)

    # Query with outerjoins to get patient details from Account or IncomingReport
    query = db.query(
        HealthReport,
        Account.nric.label('patient_nric'),
        Account.name.label('patient_name'),
        IncomingReport.info_json.label('incoming_info_json'),
        IncomingReport.nric.label('incoming_nric')
    ).outerjoin(
        Account, Account.sgimed_patient_id == HealthReport.sgimed_patient_id
    ).outerjoin(
        IncomingReport, IncomingReport.id == HealthReport.sgimed_report_id
    ).filter(
        HealthReport.sgimed_report_file_date >= start_datetime,
        HealthReport.sgimed_report_file_date < end_datetime
    )

    # Add NRIC filter if provided - search in both Account and IncomingReport
    if request.nrics:
        nric_list = [nric.strip() for nric in request.nrics.split(',') if nric.strip()]
        if nric_list:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    Account.nric.in_(nric_list),
                    IncomingReport.nric.in_(nric_list)
                )
            )

    # Get total count
    total = query.count()

    # Get paginated results
    results = query.order_by(
        HealthReport.sgimed_report_file_date.desc()
    ).offset(offset).limit(limit).all()

    # Format response - prefer Account data, fall back to IncomingReport info_json
    reports = []
    for report, nric, name, incoming_info_json, incoming_nric in results:
        patient_nric = nric
        patient_name = name

        # If no account data, try to get from IncomingReport info_json
        if not patient_nric or not patient_name:
            if incoming_info_json:
                try:
                    info = json.loads(incoming_info_json)
                    if not patient_name:
                        patient_name = info.get("patient_name")
                    if not patient_nric:
                        patient_nric = info.get("nric") or incoming_nric
                except (json.JSONDecodeError, TypeError):
                    if not patient_nric:
                        patient_nric = incoming_nric

        reports.append(HealthReportResponse(
            sgimed_hl7_id=report.sgimed_hl7_id,
            sgimed_patient_id=report.sgimed_patient_id,
            sgimed_report_id=report.sgimed_report_id,
            sgimed_report_file_date=report.sgimed_report_file_date,
            patient_nric=patient_nric,
            patient_name=patient_name,
            disclaimer_accepted_at=report.disclaimer_accepted_at,
            created_at=report.created_at,
            updated_at=report.updated_at
        ))
    
    return HealthReportListResponse(
        data=reports,
        total=total,
        page=page,
        limit=limit
    )

@router.get("/export/csv")
async def export_health_reports_csv(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db)
):
    """Export health reports as CSV for a date range"""
    
    # Date range
    start_datetime = sg_datetime.midnight(start_date)
    end_datetime = sg_datetime.midnight(end_date) + timedelta(days=1)
    
    # Query reports with patient details
    results = db.query(
        HealthReport,
        Account.nric.label('patient_nric'),
        Account.name.label('patient_name')
    ).outerjoin(
        Account, Account.sgimed_patient_id == HealthReport.sgimed_patient_id
    ).filter(
        and_(
            HealthReport.sgimed_report_file_date >= start_datetime,
            HealthReport.sgimed_report_file_date < end_datetime
        )
    ).order_by(
        HealthReport.sgimed_report_file_date.asc()
    ).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No health reports found for the specified date range")
    
    # Prepare CSV columns
    csv_cols = [
        # Patient Details
        'patient_id',
        'nric',
        'patient_name',
        'report_date',
        'disclaimer_accepted',
        # Profiles
        'clinical_assessment',
        'haematology',
        'renal_profile',
        'diabetic_panel',
        'liver_panel',
        'lipid_panel',
        'cardiac_risk_panel',
        'thyroid_function_test',
        'bone_joint_profile',
        'hepatitis_profile',
        'tumour_markers',
        'anaemia_profile',
        'std_screen',
        'others',
        'hormonal_profile',
        'urine_analysis',
        'stool_analysis',
    ] + [
        test['test_code']
        for profile in health_report_profiles
        for test in profile['tests']
    ]
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_cols)
    writer.writeheader()
    
    # Process each report
    for report, nric, name in results:
        row_data = {
            'patient_id': report.sgimed_patient_id,
            'nric': nric or '',
            'patient_name': name or '',
            'report_date': sg_datetime.sg(report.sgimed_report_file_date).strftime('%Y-%m-%d %H:%M:%S'),
            'disclaimer_accepted': 'Yes' if report.disclaimer_accepted_at else 'No'
        }
        
        # Parse report summary for profile tags
        try:
            report_summary = json.loads(report.report_summary)
            for profile in report_summary.get('profiles', []):
                profile_id = profile.get('profile_id')
                tag_id = profile.get('tag_id')
                if profile_id in csv_cols:
                    row_data[profile_id] = tag_id
        except Exception:
            pass
        
        # Get profile details
        profile_details = db.query(HealthReportProfile).filter(
            HealthReportProfile.sgimed_hl7_id == report.sgimed_hl7_id
        ).all()
        
        for profile_detail in profile_details:
            try:
                detail_report = json.loads(profile_detail.report)
                for result in detail_report.get('results', []):
                    test_code = result.get('test_code')
                    value = result.get('value', '')
                    
                    # Clean up value (remove units if present)
                    if ' ' in str(value):
                        value = str(value).split(' ')[0]
                    
                    if test_code in csv_cols:
                        row_data[test_code] = value
            except Exception:
                pass
        
        writer.writerow(row_data)
    
    # Prepare for streaming
    output.seek(0)
    
    filename = f"health_reports_{start_date}_{end_date}.csv"
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export/pdf/{sgimed_hl7_id}")
async def export_health_report_pdf(
    sgimed_hl7_id: str,
    db: Session = Depends(get_db)
):
    """Export a single health report as PDF"""
    
    # Get the health report
    report = db.query(HealthReport).filter(
        HealthReport.sgimed_hl7_id == sgimed_hl7_id
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Health report not found")

    try:
        # Get PDF from BunJS server
        fname, pdf_bytes = generate_health_report_pdf(report, db)

        # Create response
        return StreamingResponse(
            pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={fname}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


# New endpoints based on health_report_cli.py logic

class MeasurementResponse(BaseModel):
    id: str
    patient_id: str
    branch_id: str
    type_name: str
    type_unit: str
    value: str
    measurement_date: datetime
    created_at: datetime
    last_edited: datetime

class MeasurementsListResponse(BaseModel):
    patient_nric: str
    patient_name: Optional[str]
    sgimed_patient_id: str
    measurements: List[MeasurementResponse]
    total: int

class UpdateMeasurementsResponse(BaseModel):
    success: bool
    message: str
    measurements_count: int

class RegenerateHealthReportResponse(BaseModel):
    success: bool
    message: str
    reports_regenerated: int
    measurements_fetched: Optional[int] = None
    measurements_created: Optional[int] = None


@router.get("/measurements/{nric}", response_model=MeasurementsListResponse)
async def get_measurements_by_nric(
    nric: str,
    db: Session = Depends(get_db)
):
    """Get all measurements for a patient by NRIC"""

    # Find patient by NRIC
    account = db.query(Account).filter(Account.nric == nric).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"No patient found with NRIC: {nric}")

    if not account.sgimed_patient_id:
        raise HTTPException(status_code=404, detail=f"Patient {nric} does not have SGiMed patient ID")

    # Get measurements
    measurements = db.query(Measurement).filter(
        Measurement.patient_id == account.sgimed_patient_id
    ).order_by(Measurement.measurement_date.desc()).all()

    # Format response
    measurement_responses = [
        MeasurementResponse(
            id=m.id,
            patient_id=m.patient_id,
            branch_id=m.branch_id,
            type_name=m.type_name,
            type_unit=m.type_unit,
            value=m.value,
            measurement_date=m.measurement_date,
            created_at=m.created_at,
            last_edited=m.last_edited
        )
        for m in measurements
    ]

    return MeasurementsListResponse(
        patient_nric=account.nric,
        patient_name=account.name,
        sgimed_patient_id=account.sgimed_patient_id,
        measurements=measurement_responses,
        total=len(measurements)
    )


@router.post("/measurements/{nric}/update", response_model=UpdateMeasurementsResponse)
async def update_measurements_by_nric(
    nric: str,
    db: Session = Depends(get_db)
):
    """Update measurements from SGiMed for a patient by NRIC"""

    # Find patient by NRIC
    account = db.query(Account).filter(Account.nric == nric).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"No patient found with NRIC: {nric}")

    if not account.sgimed_patient_id:
        raise HTTPException(status_code=404, detail=f"Patient {nric} does not have SGiMed patient ID")

    try:
        # Fetch measurements from SGiMed
        resp = get('/measurement', {'patient_id': account.sgimed_patient_id})

        if not resp or 'data' not in resp:
            raise HTTPException(status_code=500, detail="Failed to fetch measurements from SGiMed")

        # Update measurements in database
        created_cnts, duplicate_cnts, existing_cnts = _update_measurements_cron(db, resp['data'])

        total_measurements = len(resp['data'])

        return UpdateMeasurementsResponse(
            success=True,
            message=f"Measurements updated successfully. Created: {created_cnts}, Duplicates: {duplicate_cnts}, Existing: {existing_cnts}",
            measurements_count=total_measurements
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update measurements: {str(e)}")


@router.post("/{nric}/regenerate", response_model=RegenerateHealthReportResponse)
async def regenerate_health_report_by_nric(
    nric: str,
    db: Session = Depends(get_db)
):
    """Regenerate health reports for a patient by NRIC.

    This endpoint:
    1. Finds patient by NRIC in IncomingReport table
    2. Fetches latest measurements from SGiMed API
    3. Updates measurements in database
    4. Marks all reports for regeneration
    5. Deletes cached PDFs from Supabase storage
    6. Regenerates health reports with fresh data
    """

    # Find patient by NRIC in IncomingReport table
    first_report = db.query(IncomingReport).filter(IncomingReport.nric == nric).first()
    if not first_report:
        raise HTTPException(status_code=404, detail=f"No reports found for NRIC: {nric}")

    sgimed_patient_id = first_report.patient_id

    try:
        # Step 1: Fetch and update measurements from SGiMed
        measurements_fetched = None
        measurements_created = None
        try:
            resp = get('/measurement', {'patient_id': sgimed_patient_id})
            if resp and 'data' in resp:
                created_cnts, duplicate_cnts, existing_cnts = _update_measurements_cron(db, resp['data'])
                measurements_fetched = len(resp['data'])
                measurements_created = created_cnts
                logging.info(f"Updated measurements for {nric}: fetched={measurements_fetched}, created={created_cnts}, duplicates={duplicate_cnts}, existing={existing_cnts}")
        except Exception as e:
            # Log but don't fail - measurements update is best-effort
            logging.warning(f"Failed to update measurements for {nric}: {e}")

        # Step 2: Find all incoming reports for this patient
        reports = db.query(IncomingReport).filter(
            IncomingReport.patient_id == sgimed_patient_id
        ).all()

        if not reports:
            return RegenerateHealthReportResponse(
                success=True,
                message=f"No reports found for patient {nric}",
                reports_regenerated=0,
                measurements_fetched=measurements_fetched,
                measurements_created=measurements_created
            )

        # Step 3: Mark reports for regeneration and delete PDFs from storage
        bucket = supabase.storage.from_("health-reports")
        deleted_count = 0

        for report in reports:
            report.health_report_generated = None
            try:
                bucket.remove([f"{report.id}.pdf"])
                deleted_count += 1
            except Exception:
                # Ignore if PDF doesn't exist
                pass

        db.commit()

        # Step 4: Regenerate health reports
        generate_health_reports(db)

        # Build response message
        msg_parts = [f"Successfully regenerated {len(reports)} report(s)"]
        if deleted_count > 0:
            msg_parts.append(f"deleted {deleted_count} PDF(s) from storage")
        if measurements_fetched is not None:
            msg_parts.append(f"fetched {measurements_fetched} measurements ({measurements_created} new)")

        return RegenerateHealthReportResponse(
            success=True,
            message=". ".join(msg_parts) + ".",
            reports_regenerated=len(reports),
            measurements_fetched=measurements_fetched,
            measurements_created=measurements_created
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to regenerate health reports: {str(e)}")