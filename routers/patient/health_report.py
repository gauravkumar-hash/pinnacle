from datetime import date, datetime
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import get_db
from models.document import Document, HealthReport, HealthReportProfile
from models.model_enums import DocumentType, FileViewerType
from models.patient import Account
from repository.health_report import Profile, profile_mapping, test_tag_mapping, profile_tests_mapping, tests_metadata_mapping, TestTag, PROFILE_ICON_URL
from routers.patient.document import DocumentInfo, validate_edocs_access
from routers.patient.utils import validate_firebase_token, validate_user
from utils import sg_datetime
from utils.fastapi import SuccessResp
from utils.integrations.sgimed import retrieve_sgimed_patient_id

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class TestResult(BaseModel):
    profile: Profile
    profile_icon: str
    tag: TestTag
    message: str | None = None

class ProfileBlocks(str, Enum):
    WARNING = 'warning'
    RESULTS = 'results'
    LAB_REPORT = 'lab_report'

class WarningBlock(BaseModel):
    category: TestTag | None
    type: ProfileBlocks = ProfileBlocks.WARNING
    description: str

class LabReportBlock(BaseModel):
    type: ProfileBlocks = ProfileBlocks.LAB_REPORT
    document: DocumentInfo


class HealthReportRequest(BaseModel):
    id: str
    code: str

class ReportSummaryResp(BaseModel):
    id: str
    created_at: str
    warnings: list[WarningBlock]
    results: list[TestResult]
    lab_reports: list[LabReportBlock]


def get_report(db: Session, user: Account, req: HealthReportRequest, ignore_disclaimer: bool = False):
    if user.sgimed_auth_code != req.code:
        raise HTTPException(status_code=403, detail="User does not have access to this report")
    validate_edocs_access(db, user)

    doc = db.query(Document).filter(
        Document.id == req.id,
        Document.hidden == False
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check if is dependant, if the report is before the dependant was added, and if dependant is above 21 years old
    def calculate_age(today: datetime, birth_date: date) -> int:
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    if doc.sgimed_patient_id != user.sgimed_patient_id:
        validated = False
        today = sg_datetime.now()
        for family_member in user.family_members:
            # Ensure that sgimed_patient_id is populated corrected
            if not family_member.nok_account.sgimed_patient_id:
                retrieve_sgimed_patient_id(db, family_member.nok_account)
            if not family_member.nok_account.sgimed_patient_id:
                continue

            if family_member.nok_account.sgimed_patient_id == doc.sgimed_patient_id:
                validated = True
                nok_created_at = sg_datetime.sg(family_member.created_at).replace(tzinfo=None)
                if doc.created_at and nok_created_at > doc.created_at:
                    raise HTTPException(status_code=403, detail="Report was created before dependant was added")
                if calculate_age(today, family_member.nok_account.date_of_birth) >= 21:
                    raise HTTPException(status_code=403, detail="Dependant is above 21 years old")
                break

        if not validated:
            raise HTTPException(status_code=403, detail="Report not found")

    report = db.query(HealthReport).filter(
            HealthReport.sgimed_hl7_id == doc.sgimed_document_id,
            HealthReport.sgimed_patient_id == doc.sgimed_patient_id
        ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if not ignore_disclaimer and not report.disclaimer_accepted_at:
        raise HTTPException(status_code=403, detail="Please accept the disclaimer first")

    return report

@router.post("/report/disclaimer/accept", response_model=SuccessResp)
async def accept_disclaimer(req: HealthReportRequest, user = Depends(validate_user), db: Session = Depends(get_db)):    
    report = get_report(db, user, req, ignore_disclaimer=True)
    report.disclaimer_accepted_at = sg_datetime.now()
    db.commit()
    return SuccessResp(success=True)

# Database report_summary JSON

class WarningBlockJSON(BaseModel):
    tag_id: str
    type: ProfileBlocks = ProfileBlocks.WARNING
    description: str

class ProfileSummaryJSON(BaseModel):
    profile_id: str
    tag_id: str

class ReportSummaryJSON(BaseModel):
    id: str
    created_at: str
    warnings: list[WarningBlockJSON]
    profiles: list[ProfileSummaryJSON]
    lab_report_id: str


class ProfileHeaderJSON(BaseModel):
    tag_id: str | None
    messages: list[str] = []

class TestResultJSON(BaseModel):
    test_code: str
    value: str
    desirable_range: str | None = None
    tag_id: str | None = None
    messages: list[str] | None = None

class ProfileReportJSON(BaseModel):
    profile_id: str
    overalls: list[ProfileHeaderJSON]
    results: list[TestResultJSON]
    lab_report_id: str

@router.post("/report", response_model=ReportSummaryResp)
async def get_report_summary(req: HealthReportRequest, user = Depends(validate_user), db: Session = Depends(get_db)):    
    report = get_report(db, user, req)
    report_json = ReportSummaryJSON.model_validate_json(report.report_summary)
    
    resp = ReportSummaryResp(
        id=req.id, # document_id
        created_at=report.sgimed_report_file_date.isoformat(),
        warnings=[
            WarningBlock(
                category=test_tag_mapping[w.tag_id],
                description=w.description
            ) 
            for w in report_json.warnings
        ],
        results=[
            TestResult(
                profile=profile_mapping[p.profile_id],
                profile_icon=PROFILE_ICON_URL.format(p.profile_id),
                tag=test_tag_mapping[p.tag_id],
            )
            for p in report_json.profiles
        ],
        lab_reports=[
            LabReportBlock(
                document=DocumentInfo(
                    id=report.sgimed_report_id,
                    file_type=FileViewerType.PDF,
                    file_name='Lab Report.pdf',
                    # Not Required,
                    type=DocumentType.LAB,
                    title=f'Health Report {report.sgimed_report_file_date.strftime("%d %b %Y")}.pdf',
                    subtitle='',
                )
            )
        ] if 'mock' not in report.sgimed_report_id else []
    )
    return resp

class OverallBlock(BaseModel):
    title: str
    color: str
    message: str = ''

class LabRange(BaseModel):
    value: str | None = None
    image: str | None = None
    image_ratio: float | None = None

class LabResultBlock(BaseModel):
    title: str
    value: str
    desirable_range: LabRange | None = None
    tag: TestTag | None = None
    titles: list[str] = []
    message: str | None = None

class ProfileResp(BaseModel):
    profile: Profile
    profile_icon: str
    overalls: list[OverallBlock]
    results: list[LabResultBlock]
    lab_reports: list[LabReportBlock]

# TODO: Not Needed as it should fetch from a document endpoint given the report id
# @router.post('/report/lab')
# def get_lab_report(req: HealthReportRequest, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
#     report = get_report(db, user, req)
#     resp = get(f'/incoming-report/{report.sgimed_report_id}')
#     url = resp['file_path']['link']
#     return url

@router.post('/report/{profile_req}', response_model=ProfileResp)
def get_report_profile(req: HealthReportRequest, profile_req: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    report = get_report(db, user, req)
    profile = profile_mapping.get(profile_req)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    report_profile = db.query(HealthReportProfile).filter(
        HealthReportProfile.sgimed_hl7_id == report.sgimed_hl7_id,
        HealthReportProfile.sgimed_patient_id == report.sgimed_patient_id,
        HealthReportProfile.health_profile_id == profile.id
    ).first()
    if not report_profile:
        raise HTTPException(status_code=404, detail="Report not found")

    profile_json = ProfileReportJSON.model_validate_json(report_profile.report)

    def get_lab_result_block(r: TestResultJSON):
        test_metadata = tests_metadata_mapping[r.test_code]
        
        messages = [test_metadata.get(writeup_key, None) for writeup_key in r.messages] if r.messages else []
        messages = [m for m in messages if m]
        
        desirable_range = LabRange(
            value=r.desirable_range if r.desirable_range else None,
            image=test_metadata.get('desirable_range_image', None),
            image_ratio=test_metadata.get('desirable_range_image_ratio', None)
        )
        
        return LabResultBlock(
            title=r.test_code,
            value=r.value,
            desirable_range=desirable_range if desirable_range.value or desirable_range.image else None,
            tag=test_tag_mapping[r.tag_id] if r.tag_id else None,
            message="\n\n".join(messages)
        )
        
        

    def get_overall_block(o: ProfileHeaderJSON, test_tag: TestTag):
        messages = [profile_tests_mapping[profile.id].get(m, None) for m in o.messages]
        messages = [m for m in messages if m]
        
        return OverallBlock(
            title=test_tag.title,
            color=test_tag.color,
            message="\n\n".join(messages)
        )

    return ProfileResp(
        profile=profile,
        profile_icon=PROFILE_ICON_URL.format(profile.id),
        overalls=[
            get_overall_block(o, test_tag_mapping[o.tag_id])
            for o in profile_json.overalls
            if o.tag_id
        ],
        results=[
            get_lab_result_block(r)
            for r in profile_json.results
        ],
        lab_reports=[
            LabReportBlock(
                document=DocumentInfo(
                    id=report.sgimed_report_id,
                    file_type=FileViewerType.PDF,
                    file_name='Lab Report.pdf',
                    # Not Required,
                    type=DocumentType.LAB,
                    title=f'Health Report {report.sgimed_report_file_date.strftime("%d %b %Y")}.pdf',
                    subtitle='',
                )
            )
        ] if 'mock' not in report.sgimed_report_id else []
    )
