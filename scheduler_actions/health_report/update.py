from sqlalchemy import or_
from repository.health_report import ProfileReportResp, ProfileSummary, ReportSummaryResp, TestTags, WarningBlock
from models import Document, DocumentStatus, DocumentType, HealthReport, HealthReportProfile
from datetime import datetime
from sqlalchemy.orm import Session

import pytz
sgtz = pytz.timezone("Asia/Singapore") 
# def sg(dt: datetime):
#     return dt.replace(tzinfo=pytz.utc).astimezone(sgtz)

def save_health_report_to_db(db: Session, hl7_id: str, report_id: str, patient_id: str, report_created_at: datetime, patient_profiles: list[ProfileReportResp]):
    # for report_id, patient_details in tqdm(processed_reports.items()):
    #     if report_id not in patient_measurements_dict:
    #         continue
    #     if report_id not in patient_profiles_dict:
    #         continue

    #     patient_measurements = patient_measurements_dict[report_id]
    #     patient_profiles = patient_profiles_dict[report_id]
    
    # hl7_id = patient_details['hl7s'][0]['id']
    # report_id = patient_details['report']['id']
    # report_created_at = datetime.strptime(patient_details['report']['last_edited'] + "+08:00", '%Y-%m-%d %H:%M:%S%z')
    # Redundancy to ensure patient id is correctly loaded
    # patient_id = patient_details['report']['patient']['id']
    # if not patient_id:
    #     patient_id = patient_details['hl7s'][0]['patient_id']

    profile_records = []
    for profile in patient_profiles:
        profile_id = profile.profile_id
        profile_record = HealthReportProfile(
            sgimed_hl7_id=hl7_id,
            health_profile_id=profile_id,
            sgimed_patient_id=patient_id,
            report=profile.model_dump_json()
        )
        profile_records.append(profile_record)
        

    # Generate Warnings
    warnings = []
    result_tags = [profile.overalls[0].tag_id for profile in patient_profiles]
    if TestTags.OUT_OF_RANGE.value.id in result_tags:
        warnings.append(WarningBlock(
            tag_id=TestTags.OUT_OF_RANGE.value.id,
            description='Some of your test results are **out of the reference range**. You are encouraged to consult the doctor for further medical advice.',
        ))
        
    if TestTags.BORDERLINE.value.id in result_tags:
        warnings.append(WarningBlock(
            tag_id=TestTags.BORDERLINE.value.id,
            description='Some of your tests results are **borderline**. You are encouraged to consult the doctor for further medical advice.',
        ))

    # Generate Report Summary
    report_summary = ReportSummaryResp(
        id=hl7_id,
        created_at=report_created_at.isoformat(),
        warnings=warnings,
        profiles=[
            ProfileSummary(
                profile_id=profile.profile_id,
                tag_id=profile.overalls[0].tag_id,
            )
            for profile in patient_profiles
        ],
        lab_report_id=report_id,
    )

    report_record = HealthReport(
        sgimed_hl7_id=hl7_id,
        sgimed_hl7_content='', # patient_details['hl7s'][0]['hl7_content'],
        sgimed_patient_id=patient_id,
        patient_test_results='', # json.dumps(patient_measurements),
        sgimed_report_id=report_id,
        sgimed_report_file_date=report_created_at.replace(tzinfo=pytz.utc),
        report_summary=report_summary.model_dump_json(),
    )

    # Create Document Record
    doc = Document(
        sgimed_patient_id=patient_id,
        sgimed_document_id=hl7_id,
        sgimed_branch_id='',
        name='Health Report (App)',
        hidden=False,
        document_date=report_created_at.date(),
        document_type=DocumentType.HEALTH_SCREENING,
        status=DocumentStatus.APP_HEALTH_REPORT,
        notification_sent=False,
        # Required to be same as SGiMed timings as all documents are created in SG timing
        created_at=report_created_at.replace(tzinfo=pytz.utc),
        updated_at=report_created_at.replace(tzinfo=pytz.utc),
    )

    db.query(Document).filter(Document.sgimed_document_id == hl7_id).delete()
    db.query(HealthReportProfile).filter(HealthReportProfile.sgimed_hl7_id == hl7_id).delete()
    db.query(HealthReport).filter(or_(HealthReport.sgimed_hl7_id == hl7_id, HealthReport.sgimed_report_id == report_id)).delete()

    # with open('profile_records.json', 'a') as f:
    #     f.write("==== Report ID: " + report_id + " ====\n")
    #     for profile_record in profile_records:
    #         json.dump(profile_record.as_dict(), f, indent=4, default=str)
    #         f.write('\n===\n')
    #     json.dump(report_record.as_dict(), f, indent=4, default=str)
    #     f.write('\n===\n')
    #     json.dump(doc.as_dict(), f, indent=4, default=str)
    #     f.write('\n===\n')

    # Save to Database
    for profile_record in profile_records:
        db.add(profile_record)
    db.add(report_record)
    db.add(doc)
    
    db.commit()

    return doc, report_record