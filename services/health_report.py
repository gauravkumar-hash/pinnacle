from config import supabase
from supabase import StorageException
from fastapi import HTTPException
from models import HealthReport, HealthReportProfile, IncomingReport, Account
from sqlalchemy.orm import Session
from utils.integrations.bunjs_server import get_health_report_pdf
from utils.integrations.sgimed_documents import get_document, get_sgimed_report
import json
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import requests

def generate_health_report_pdf(report: HealthReport, db: Session):
    merged_fname = f"Health Report {report.sgimed_report_file_date.strftime('%d %b %Y')}.pdf"
    
    # Fetch from Cache
    bucket = supabase.storage.from_("health-reports")
    supabase_cache_path = f"{report.sgimed_report_id}.pdf"
    try:
        pdf_bytes = bucket.download(supabase_cache_path)
        # Stream the file
        return merged_fname, BytesIO(pdf_bytes)
        # return StreamingResponse(
        #     BytesIO(pdf_bytes), 
        #     media_type="application/pdf", 
        #     headers={"Content-Disposition": f'inline; filename="{merged_fname}"'}
        # )
    except StorageException:
        pass

    acc = db.query(Account).filter(Account.sgimed_patient_id == report.sgimed_patient_id).first()
    profile_details = db.query(HealthReportProfile).filter(
        HealthReportProfile.sgimed_hl7_id == report.sgimed_hl7_id,
        HealthReportProfile.sgimed_patient_id == report.sgimed_patient_id,
    ).all()

    # Generate Health Report PDF through Supabase Functions
    incoming_report = db.query(IncomingReport).filter(IncomingReport.id == report.sgimed_report_id).first()

    # Use account details if available, otherwise fall back to incoming report info_json
    if acc:
        header_name = acc.name
        header_nric = acc.nric
        header_gender = acc.gender.value if acc.gender else "N/A"
    elif incoming_report:
        # Parse info_json from incoming report
        try:
            info = json.loads(incoming_report.info_json) if incoming_report.info_json else {}
        except (json.JSONDecodeError, TypeError):
            info = {}
        header_name = info.get("patient_name") or "N/A"
        header_nric = info.get("nric") or incoming_report.nric or report.sgimed_patient_id
        header_gender = info.get("gender") or "N/A"
    else:
        header_name = "N/A"
        header_nric = report.sgimed_patient_id
        header_gender = "N/A"

    payload = {
        "header": {
            'name': header_name,
            'identity_number': header_nric,
            'gender': header_gender,
            'report_date': report.sgimed_report_file_date.strftime("%d %b %Y"),
            'lab_reference_number': incoming_report.report_file_id if incoming_report else report.sgimed_report_id,
        },
        'summary': json.loads(report.report_summary),
        'profiles': {
            profile_detail.health_profile_id: json.loads(profile_detail.report)
            for profile_detail in profile_details
        },
    }
    # health_report_bytes = supabase.functions.invoke(
    #     "health-report-pdf",
    #     {
    #         "body": payload,
    #         "responseType": "binary",
    #         "headers": {"Content-Type": "application/json"},
    #     },
    # )
    health_report_bytes = get_health_report_pdf(payload)
    if not isinstance(health_report_bytes, bytes):
        raise HTTPException(500, "Failed to generate health report")

    # Fetch PDF from SGiMed
    lab_report_bytes = None
    try:        
        # Try to fetch /incoming-report endpoint, if fails, try to fetch /document endpoint
        try:
            doc = get_sgimed_report(report.sgimed_report_id)
        except:
            print("Fetching Document since not in Incoming Report")
            doc = get_document(report.sgimed_report_id)

        response = requests.get(str(doc.file_path.link))
        if response.status_code != 200:
            raise HTTPException(404, "Failed to fetch document. please contact an administrator")
        lab_report_bytes = response.content
    except Exception as e:
        # logging.error(f"Health Report: Failed to fetch lab report from SGiMed. Report ID: {report.sgimed_report_id}, {e}", exc_info=True)
        # raise HTTPException(404, "Failed to fetch document. please contact an administrator")
        return merged_fname, BytesIO(health_report_bytes)
        # return StreamingResponse(
        #     BytesIO(health_report_bytes),
        #     media_type="application/pdf",
        #     headers={"Content-Disposition": f"inline; filename={merged_fname}"},
        # )

    # Create PdfReader object from bytes
    hr_reader = PdfReader(BytesIO(health_report_bytes))
    lr_reader = PdfReader(BytesIO(lab_report_bytes))
    # Merge PDFs
    pdf_writer = PdfWriter()
    pdf_writer.append(hr_reader)
    pdf_writer.append(lr_reader)
    # Generate merged bytes
    merged_buffer = BytesIO()
    pdf_writer.write(merged_buffer)
    merged_pdf_bytes = merged_buffer.getvalue()
    # Close all readers and writers
    hr_reader.close()
    lr_reader.close()
    pdf_writer.close()
    
    # Upload to Supabase
    bucket.upload(supabase_cache_path, merged_pdf_bytes, {"content-type": "application/pdf", "upsert": "true"})
    return merged_fname, BytesIO(merged_pdf_bytes)
    # return StreamingResponse(
    #     BytesIO(merged_pdf_bytes),
    #     media_type="application/pdf",
    #     headers={"Content-Disposition": f"inline; filename={merged_fname}"},
    # )