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
class ProfileReportResp(BaseModel):
    profile_id: str
    # ─────────────────────────────────────────────────────────────────────────
    # FIX: Added profile_name field.
    #
    # Defaults to None so all existing DB records (saved before this field
    # existed) remain valid — Pydantic will just set it to None on load.
    #
    # The frontend/PDF renderer should:
    #   1. Use profile_name when it is not None  (new records)
    #   2. Fall back to ProfilesEnum[profile_id].title  (old records)
    # ─────────────────────────────────────────────────────────────────────────
    profile_name: str | None = None
    overalls: list[ProfileHeader]
    results: list[TestResult]
    lab_report_id: str


DEFAULT_HL7_SUPPORTED_PROFILES = [
    '^PLHS1', '^PLHS2', '^PLHS3', '^PLHS4', '^PLHS5', '^PLHS6', '^PLHS7', '^PLHS8', '^PLHS9',
    '^PLKF0', '^PLKF1', '^PLKF2', '^PLKF3', '^PLKF4', '^PLKF5', '^PLKF6', '^PLKF7', '^PLKF8', '^PLKF9',
    '^PHS10', '^PHS1A', '^PKF10', '^PKF1A', '^PSG60', '^PHS5C',
    '^PKF1H', '^PHS1H', '^PKF5H', '^PHS5H',
    '^PLNY1', '^PLNY2', '^PLNY3', '^PLNY4', '^PLNY5',
    '^NY1KF', '^NY2UB', '^NY3UB', '^NY4UB', '^NY5UB',
]

ALWAYS_SUPPORTED_HL7_PROFILES = [
    '^PARC1',
    '^PARC2',
]

def get_supported_hl7_profiles(configured_profiles=None):
    profiles = configured_profiles or DEFAULT_HL7_SUPPORTED_PROFILES
    return list(dict.fromkeys([*profiles, *ALWAYS_SUPPORTED_HL7_PROFILES]))

def is_hl7_profile_supported(hl7_content: str, configured_profiles=None):
    return any(
        profile in hl7_content
        for profile in get_supported_hl7_profiles(configured_profiles)
    )
