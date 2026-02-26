from models.model_enums import SGiMedGender
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session
from models import HL7Log, IncomingReport, SessionLocal, Measurement, Account
# Extract Measurements
from pydantic import BaseModel, model_validator, field_validator
from datetime import datetime, timedelta
from typing import Self
# Extract Gender from Lab Report
from hl7apy.consts import VALIDATION_LEVEL
from hl7apy.core import ElementList
from hl7apy.parser import parse_segment
import re

def main():
    with SessionLocal() as db:
        reports = db.query(IncomingReport).filter(
            or_(
                IncomingReport.health_report_generated == False,
                IncomingReport.health_report_generated == None
            )
        ).limit(400).all()
        for report in reports:
            patient_details_json = get_report_measurements(db, report)
            if patient_details_json:
                print(patient_details_json)
                break


def get_report_measurements(db: Session, report: IncomingReport):
    # Ensure report_file_id is not None since it is using a like query match
    if not report.report_file_id:
        logging.error(f"Incoming Report {report.id}: report_file_id not found")
        return None, None
    # Ensure report_file_id is 7 characters long, but do not interrupt logic
    if not len(report.report_file_id) == 7:
        logging.error(f"Incoming Report {report.id}: report_file_id '{report.report_file_id}' length is not 7")

    # Incoming Reports are only processed upon Completion. Thus, HL7 should always exists, if not it means report is not to be processed
    # 1. Failed: report_id format in HL7 changes
    # hl7 = db.query(HL7Log).filter(HL7Log.report_file_id == report.report_file_id).order_by(HL7Log.created_at.desc()).first()
    # 2. Failed: report_id in HL7 is different from incoming report
    hl7 = db.query(HL7Log).filter(
        HL7Log.nric == report.nric, 
        HL7Log.report_file_id.like(f'%{report.report_file_id}%')
    ).order_by(HL7Log.created_at.desc()).first()
    # 3. Given HL7Log.created_at timing is usually aligned with IncomingReport.file_date, take 1 day difference
    # start_date = report.file_date - timedelta(hours=12)
    # end_date = report.file_date + timedelta(hours=12)
    # hl7 = db.query(HL7Log).filter(
    #     HL7Log.nric == report.nric,
    #     HL7Log.created_at >= start_date,
    #     HL7Log.created_at <= end_date,
    # ).order_by(HL7Log.created_at.desc()).first()
    if not hl7:
        return None, None

    # Convert HL7 to JSON
    patient_details_json = hl7_to_json(hl7.hl7_content)
    if 'GENDER' not in patient_details_json:
        account = db.query(Account).filter(Account.nric == report.nric).first()
        if account:
            if account.gender == SGiMedGender.MALE:
                patient_details_json['GENDER'] = 'M'
            elif account.gender == SGiMedGender.FEMALE:
                patient_details_json['GENDER'] = 'F'
            logging.info(f"Incoming Report {report.id}: Gender not found in HL7. Using Account Gender: {patient_details_json['GENDER']}")

    if 'GENDER' not in patient_details_json:
        logging.error(f"Incoming Report {report.id}: Gender not found in HL7. STOPPED generating Health Repor")
        return None, None

    patient_id = hl7.patient_id

    # Get Measurements from Database
    measurements_list = db.query(Measurement).filter(
        Measurement.patient_id == patient_id,
        # Measurement date should be within +-3 days of report file date
        Measurement.measurement_date > report.file_date - timedelta(days=30),
        Measurement.measurement_date < report.file_date + timedelta(days=3)
    ).order_by(Measurement.measurement_date.asc()).all()
    if measurements_list:
        measurements = get_patient_measurement(patient_id, measurements_list)
        patient_details_json.update(measurements)

    return hl7, patient_details_json

def hl7_to_json(hl7_text: str):
    hl7_json = {}
    for seg in hl7_text.split("\n"):
        if not seg: continue
        segment = parse_segment(seg, validation_level=VALIDATION_LEVEL.TOLERANT)
        data: ElementList = segment.children

        if 'PID_8' in data.indexes: # type: ignore
            gender = data.indexes['PID_8'][0].value # type: ignore
            hl7_json['GENDER'] = [gender, None, None]
            continue
        
        if segment.name == "OBR":
            data: ElementList = segment.children
            package_name = data.indexes['OBR_4'][0].value # type: ignore
            if package_name.startswith('0^'):
                if 'PROFILE' not in hl7_json:
                    hl7_json['PROFILE'] = []
                hl7_json['PROFILE'].append(package_name[:7])
            continue

        if 'OBX_3' not in data.indexes: # type: ignore
            continue

        test_key = data.indexes['OBX_3'][0].value # type: ignore
        value = data.indexes['OBX_5'][0].value # type: ignore
        unit = data.indexes['OBX_6'][0].value if 'OBX_6' in data.indexes else None # type: ignore
        lab_range = data.indexes['OBX_7'][0].value if 'OBX_7' in data.indexes else None # type: ignore

        match = re.match(r'^.+\^.+\^', test_key)
        if match:
            test_key = match.group()

        hl7_json[test_key] = [value, unit, lab_range]
    return hl7_json

class SGiMedMeasurementType(BaseModel):
    id: str
    name: str
    unit: str

class SGiMedMeasurement(BaseModel):
    id: str
    type: SGiMedMeasurementType
    value: str
    branch_id: str
    date: str | None = None
    measure_date: str | None = None
    # measure_time: str | None
    created_at: datetime = datetime.now()

    @model_validator(mode='after')
    def combine_time(self) -> Self:
        if self.measure_date:
            self.created_at = datetime.fromisoformat(self.measure_date)
        elif self.date:
            self.created_at = datetime.fromisoformat(self.date)
        return self

class SGiMedIdName(BaseModel):
    id: str
    name: str

class SGiMedIncomingPatient(SGiMedIdName):
    nric: str | None

class SGiMedIncomingReport(BaseModel):
    id: str
    patient: SGiMedIncomingPatient
    vendor: str
    status: str
    branch_id: str
    visit_id: str | None = None
    file_name: str
    file_date: datetime # UTC time
    info_json: str | None = None
    last_edited: str

    @field_validator("file_date", mode="before")
    @classmethod
    def transform_file_date(cls, raw: str) -> datetime:
        return datetime.fromisoformat(raw)


def get_patient_measurement(patient_id: str, measurements: list[Measurement]):
    # measurements = [SGiMedMeasurement.model_validate(row) for row in measurement_list]
    # measurements: list[SGiMedMeasurement] = sorted([row for row in measurements if row.created_at < report_time], key=lambda x: x.created_at, reverse=True)
    # if not measurements:
    #     return {}

    keys = ["Systolic", "Diastolic", "Height", "Weight"]
    measures_dict = {}
    measures_check_dict = {} # Used for sanity check
    row = measurements[0]
    for row in measurements:
        key = row.type_name
        # Unlock this, TODO: compute time difference between report and measurement datetime
        # if key in keys and key not in measures_dict:
        if key in keys:
            if key in measures_dict:
                continue

            measures_dict[f'SGiMed^{key}'] = [row.value, row.type_unit, None]
            measures_check_dict[f'SGiMed^{key}'] = row.created_at.strftime('%Y-%m-%d %H:%M:%S')

    if 'SGiMed^Systolic' in measures_dict and 'SGiMed^Diastolic' in measures_dict:
        if measures_check_dict['SGiMed^Systolic'] != measures_check_dict['SGiMed^Diastolic']:
            print(f"Error: Patient {patient_id} BP measurements timings are not the same. {measures_check_dict['SGiMed^Systolic']} != {measures_check_dict['SGiMed^Diastolic']}")
        #     del measures_dict['SGiMed^Systolic']
        #     del measures_dict['SGiMed^Diastolic']
        # else:
        try:
            float(measures_dict['SGiMed^Systolic'][0])
            float(measures_dict['SGiMed^Diastolic'][0])
            measures_dict['SGiMed^BP'] = [f'{measures_dict["SGiMed^Systolic"][0]}/{measures_dict["SGiMed^Diastolic"][0]}', measures_dict["SGiMed^Systolic"][1], None]
        except ValueError:
            print(f"Error: Patient {patient_id} value {measures_dict['SGiMed^Systolic'][0]} or {measures_dict['SGiMed^Diastolic'][0]} cannot be converted to float")
    else:
        if 'SGiMed^Systolic' in measures_dict:
            print(f"Error: Patient {patient_id} missing measurements: SGiMed^Diastolic")
            del measures_dict['SGiMed^Systolic']
        elif 'SGiMed^Diastolic' in measures_dict:
            print(f"Error: Patient {patient_id} missing measurements: SGiMed^Systolic")
            del measures_dict['SGiMed^Diastolic']

    if 'SGiMed^Height' in measures_dict and 'SGiMed^Weight' in measures_dict:
        if measures_check_dict['SGiMed^Height'] != measures_check_dict['SGiMed^Weight']:
            print(f"Warning: Patient {patient_id} Height and Weight measurements timings are not the same. {measures_check_dict['SGiMed^Height']} != {measures_check_dict['SGiMed^Weight']}")
        
        try:
            measures_dict['SGiMed^BMI'] = [str(round(float(measures_dict["SGiMed^Weight"][0]) / ((float(measures_dict["SGiMed^Height"][0])/100)**2), 1)), 'kg/m2', None]
        except ValueError:
            print(f"Error: Patient {patient_id} value {measures_dict['SGiMed^Height'][0]} or {measures_dict['SGiMed^Weight'][0]} cannot be converted to float")
    else:
        if 'SGiMed^Height' in measures_dict:
            print(f"Error: Patient {patient_id} missing measurements: SGiMed^Weight")
            del measures_dict['SGiMed^Height']
        elif 'SGiMed^Weight' in measures_dict:
            print(f"Error: Patient {patient_id} missing measurements: SGiMed^Height")
            del measures_dict['SGiMed^Weight']

    return measures_dict

if __name__ == "__main__":
    main()
