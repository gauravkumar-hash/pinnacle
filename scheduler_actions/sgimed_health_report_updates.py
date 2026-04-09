import logging
from .common import CronLogAPI
from utils.integrations.sgimed import get
from sqlalchemy.orm import Session
from datetime import datetime
from utils.system_config import get_config_value
from utils.notifications import send_patient_notification
from models import HL7Log, IncomingReport, Document, Measurement, Account
from repository.health_report import TestTags
import re
from .health_report.convert import get_report_measurements
from .health_report.process import generate_profile_output
from .health_report.update import save_health_report_to_db
from hl7apy.parser import parse_segment

default_hl7_supported_profiles = [
    '^PLHS1','^PLHS2','^PLHS3','^PLHS4','^PLHS5','^PLHS6','^PLHS7','^PLHS8','^PLHS9', # - PLHS1-9
    '^PLKF0','^PLKF1','^PLKF2','^PLKF3','^PLKF4','^PLKF5','^PLKF6','^PLKF7','^PLKF8','^PLKF9', # - ⁠PLKF0-9
    '^PHS10','^PHS1A','^PKF10','^PKF1A','^PSG60','^PHS5C', # - ⁠PHS10, ⁠PHS1A, ⁠PKF10, ⁠PKF1A, ⁠PSG60, ⁠PHS5C
    '^PKF1H','^PHS1H','^PKF5H','^PHS5H', # Added on 22 Mar
    '^PLNY1', '^PLNY2', '^PLNY3', '^PLNY4', '^PLNY5',  # HS Only: Basic, Intermediate, Executive 1, Executive 2, Comprehensive
    '^NY1KF', '^NY2UB', '^NY3UB', '^NY4UB', '^NY5UB',  # HS + NK: Basic, Intermediate, Executive 1, Executive 2, Comprehensive
]

def update_hl7_logs_cron(db: Session):
    cron = CronLogAPI(db, 'sgimed_hl7_logs_cron', '/hl7-log')
    if len(cron.data) == 0:
        return
    
    created_cnts = 0
    existing_cnts = 0
    
    # Get Existing HL7 Log IDs
    unique_ids = set([row['id'] for row in cron.data])
    existing_records = db.query(HL7Log.id, HL7Log.last_edited).filter(HL7Log.id.in_(unique_ids)).all()
    existing_records_map = {row[0]: row[1] for row in existing_records}
    
    hl7_supported_profiles: list = get_config_value(db, 'HL7_SUPPORTED_PROFILES', default_hl7_supported_profiles) # type: ignore
    for row in cron.data:
        # As long as one matches, keep the HL7 profile
        profile_supported = False
        for profile in hl7_supported_profiles:
            if profile in row['hl7_content']:
                profile_supported = True
                break
        if not profile_supported:
            continue

        # Check for existing record
        if row['id'] in existing_records_map:
            existing_cnts += 1
            if existing_records_map[row['id']].strftime("%Y-%m-%d %H:%M:%S") != row['last_edited']:
                logging.error(f'HL7 log {row["id"]} has been updated since last cron job')
            continue
        
        created_cnts += 1
        # Try to find Patient ID if it is not present
        patient_id = row['patient_id']
        if not patient_id:
            # Don't have ID and NRIC, skip
            if not row['nric']:
                continue
            resp = get('/patient', { 'nric': row['nric'] })
            if len(resp['data']) == 0:
                logging.error(f'HL7 log {row["id"]} patient NRIC ID not found')
                continue            
            patient_id = resp['data'][0]['id']

        # Extract Report File ID from hl7_content
        report_file_id = ''
        try:
            seg = parse_segment(row['hl7_content'].split('\n')[0])
            if 'MSH_10' in seg.children.indexes: # type: ignore
                report_file_id = seg.children.indexes['MSH_10'][0].value # type: ignore
        except Exception:
            logging.error(f'HL7 log {row["id"]} failed to parse report_file_id')

        # Create new record
        hl7_log = HL7Log(
            id=row['id'],
            vendor=row['vendor'],
            nric=row['nric'],
            branch_id=row['branch_id'],
            patient_id=patient_id,
            report_file_id=report_file_id,
            hl7_content=row['hl7_content'],
            last_edited=row['last_edited'],
            created_at=row['created_at']
        )
        db.add(hl7_log)

    cron.commit()
    print(f"HL7 logs Cron: {cron.cron_log.last_modified}, Created {created_cnts}, Existing {existing_cnts}")

def update_incoming_reports_cron(db: Session):
    cron = CronLogAPI(db, 'sgimed_incoming_reports_cron', '/incoming-report')
    if len(cron.data) == 0:
        return

    created_cnts = 0
    existing_cnts = 0

    # Get Existing Incoming Report IDs
    unique_ids = set([row['id'] for row in cron.data])
    existing_records = db.query(IncomingReport.id, IncomingReport.last_edited).filter(IncomingReport.id.in_(unique_ids)).all()
    existing_records_map = {row[0]: row[1] for row in existing_records}

    for row in cron.data:
        # Skip waiting reports
        if row['status'] == 'waiting':
            continue

        # Check for existing record
        if row['id'] in existing_records_map:
            existing_cnts += 1
            if existing_records_map[row['id']].strftime("%Y-%m-%d %H:%M:%S") != row['last_edited']:
                logging.error(f'Incoming report {row["id"]} has been updated since last cron job')
            
            # If report already exists, and health report was generated, hide the health report
            if row['status'] == 'deleted':
                record = db.query(IncomingReport).filter(IncomingReport.id == row['id']).first()
                if not record:
                    logging.error(f'Incoming report {row["id"]} not found, for row status {row["status"]}')
                    continue
                if record.health_report_generated:
                    hl7_ids = db.query(HL7Log.id).filter(HL7Log.report_file_id == record.report_file_id).all()
                    hl7_ids = [hl7_id[0] for hl7_id in hl7_ids]
                    doc = db.query(Document).filter(Document.sgimed_document_id.in_(hl7_ids)).first()
                    if doc:
                        doc.hidden = True
                        record.health_report_generated = False
                        db.commit()
            continue
        
        # Only process completed records
        if row['status'] == 'deleted':
            continue

        # Extract Report File ID from file name
        match = re.search(r'^Pathlab-.+?-(\d+)\.pdf$', row['file_name'])
        report_file_id = str(int(match.group(1))) if match else ''

        # Create new record
        created_cnts += 1
        incoming_report = IncomingReport(
            id=row['id'],
            patient_id=row['patient']['id'],
            nric=row['patient']['nric'] if row['patient']['nric'] else '',
            vendor=row['vendor'],
            status=row['status'],
            branch_id=row['branch_id'],
            visit_id=row['visit_id'] if row['visit_id'] else '',
            file_name=row['file_name'],
            report_file_id=report_file_id,
            file_date=row['file_date'],
            info_json=row['info_json'] if row['info_json'] else '',
            last_edited=row['last_edited'],
        )
        db.add(incoming_report)

    cron.commit()
    print(f"Incoming reports Cron: {cron.cron_log.last_modified}, Created {created_cnts}, Existing {existing_cnts}")

def _update_measurements_cron(db: Session, data: list):
    ids_created = []
    created_cnts = 0
    duplicate_cnts = 0
    existing_cnts = 0
    # Get Existing Measurement IDs
    unique_ids = set([row['id'] for row in data])
    existing_records = db.query(Measurement.id, Measurement.last_edited).filter(Measurement.id.in_(unique_ids)).all()
    existing_records_map = {row[0]: row[1] for row in existing_records}

    for row in data:
        # Skip if already created
        if row['id'] in ids_created:
            # logging.error(f'Measurement {row["id"]} already created')
            duplicate_cnts += 1
            continue
    
        if not row['patient']:
            continue

        # Combine date and time into a single datetime object
        measurement_date = row['date']
        if row['time']:
            measurement_date = measurement_date[:11] + row['time'] + measurement_date[19:]
        measurement_date = datetime.strptime(measurement_date, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
        row_data = {
            'id': row['id'],
            'patient_id': row['patient']['id'],
            'branch_id': row['branch_id'],
            'type_name': row['type']['name'],
            'type_unit': row['type']['unit'],
            'value': row['value'],
            'measurement_date': measurement_date,
            'last_edited': row['last_edited'],
            'created_at': row['created_at'],
        }

        ids_created.append(row['id'])
        # Check for existing record
        if row['id'] in existing_records_map:
            existing_cnts += 1
            # if record.last_edited.strftime("%Y-%m-%d %H:%M:%S") != row['last_edited']:
            if existing_records_map[row['id']].strftime("%Y-%m-%d %H:%M:%S") != row['last_edited']:
                # print("Updating record due to last_edited mismatch")
                record = db.query(Measurement).filter(Measurement.id == row['id']).first()
                if record:
                    record.update_vars(row_data)
                else:
                    print(f"Updated record but record not found for {row['id']}")
            continue

        # Combine date and time into a single datetime object
        measurement_date = row['date']
        if row['time']:
            measurement_date = measurement_date[:11] + row['time'] + measurement_date[19:]
        measurement_date = datetime.strptime(measurement_date, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)

        # Create new record
        created_cnts += 1
        measurement = Measurement(**row_data)
        db.add(measurement)
        ids_created.append(row['id'])
    db.commit()
    return created_cnts, duplicate_cnts, existing_cnts

def update_measurements_cron(db: Session, data = None):
    cron = CronLogAPI(db, 'sgimed_measurements_cron', '/measurement', sort_order='DESC')
    if len(cron.data) == 0:
        return

    created_cnts, duplicate_cnts, existing_cnts = _update_measurements_cron(db, cron.data)
    cron.commit()
    print(f"Measurement Cron: {cron.cron_log.last_modified}, page {cron.cron_log.last_page}. Created {created_cnts}, Duplicates {duplicate_cnts}, Existing {existing_cnts}")

def generate_health_reports(db: Session):
    reports = db.query(IncomingReport).filter(
        # Default Settings
        IncomingReport.status == 'completed',
        IncomingReport.health_report_generated == None,
    ).all()

    report_cnts = 0
    for report in reports:
        try:
            # Convert HL7, Measurements into JSON Format
            hl7, measurements = None, None
            if report.vendor == 'PathLab':
                hl7, measurements = get_report_measurements(db, report)
            if not hl7 or not measurements:
                report.health_report_generated = False
                db.commit()
                continue

            # Process Measurements into Health Reports JSON
            profiles = generate_profile_output(report.id, measurements)

            # Save / Update into Database
            doc, report_record = save_health_report_to_db(
                db,
                hl7.id,
                report.id,
                report.patient_id,
                report.file_date,
                profiles
            )
            
            # Send Patient Notification
            # Check if user has an account and notification token
            user = db.query(Account).filter(Account.sgimed_patient_id == hl7.patient_id).first()
            if user:
                result_tags = [profile.overalls[0].tag_id for profile in profiles]
                msg = 'Your laboratory and health reports are ready for viewing. Please click "My Reports" to access.'
                if TestTags.OUT_OF_RANGE.value.id in result_tags or TestTags.BORDERLINE.value.id in result_tags:
                    msg = 'Your laboratory and health reports are ready for viewing. Please click "My Reports" to access. Note: Some of your test results are out of the reference range. You are encouraged to consult the doctor for further medical advice.'
                send_patient_notification(user, "Health Report Uploaded", msg)
                doc.notification_sent = True

            report.health_report_generated = True
            if report_cnts % 100 == 0:
                db.commit()
            report_cnts += 1
        except Exception as e:
            logging.error(f"Error generating health report for report {report.id}: {e}")
            db.commit()

    print(f"Generated {report_cnts} health reports")
    db.commit()
