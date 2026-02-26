from enum import Enum
from pydantic import BaseModel

class Profile(BaseModel):
    id: str
    icon: str | None = None
    title: str

class TestTagColor(str, Enum):
    RED = 'red'
    ORANGE = 'orange'
    GREEN = 'green'

class TestTag(BaseModel):
    id: str
    title: str
    color: TestTagColor   

class TestTags(Enum):
    NORMAL = TestTag(id='normal', title='Normal', color=TestTagColor.GREEN)
    BORDERLINE = TestTag(id='borderline', title='Borderline', color=TestTagColor.ORANGE)
    OUT_OF_RANGE = TestTag(id='out_of_range', title='Out of Range', color=TestTagColor.RED)

class ProfileSummary(BaseModel):
    profile_id: str
    tag_id: str | None

class ProfileBlocks(str, Enum):
    WARNING = 'warning'
    RESULTS = 'results'
    LAB_REPORT = 'lab_report'

class WarningBlock(BaseModel):
    tag_id: str
    type: ProfileBlocks = ProfileBlocks.WARNING
    description: str

class LabReportBlock(BaseModel):
    type: ProfileBlocks = ProfileBlocks.LAB_REPORT
    report_id: str

class ProfileHeader(BaseModel):
    tag_id: str | None
    messages: list[str] = []

class LabRange(BaseModel):
    value: str | None = None
    image: str | None = None
    image_ratio: float | None = None

class TestResult(BaseModel):
    test_code: str
    value: str
    desirable_range: str | None = None
    tag_id: str | None = None
    messages: list[str] | None = None

# Endpoint 1
class ReportSummaryResp(BaseModel):
    id: str
    created_at: str
    warnings: list[WarningBlock]
    profiles: list[ProfileSummary]
    lab_report_id: str

# Endpoint 2
# Icon - https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/health_reports/icons/{id}.png
# Writeup Mapping
class ProfileReportResp(BaseModel):
    profile_id: str
    overalls: list[ProfileHeader]
    results: list[TestResult]
    lab_report_id: str
