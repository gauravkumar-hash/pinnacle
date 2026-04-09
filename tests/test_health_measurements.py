"""
Standalone verification tests for the new health measurements:
  - WHR (Waist-Hip Ratio) calculation
  - Tonometry mapping
  - Visual Acuity mapping
  - Colour Vision mapping
  - Body Fat Percentage mapping
  - Visceral Fat mapping
  - Spirometry mapping
  - get_patient_measurement() extraction logic (mocked DB rows)

Run with:
    cd /home/gaurav/pinnacle/pinnacle-main
    python -m pytest tests/test_health_measurements.py -v
  or just:
    python tests/test_health_measurements.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from dataclasses import dataclass
from typing import Optional


# ─── Minimal stubs so we don't need a DB ────────────────────────────────────

@dataclass
class FakeMeasurement:
    type_name: str
    value: str
    type_unit: str = ""
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime(2026, 4, 1, 9, 0, 0)


def make_measurements(*rows):
    """Helper: create FakeMeasurement list from (type_name, value) tuples."""
    return [FakeMeasurement(type_name=t, value=v) for t, v in rows]


# ─── Import the real functions under test ───────────────────────────────────

from scheduler_actions.health_report.convert import get_patient_measurement  # noqa: E402
from repository.health_report.mapping import (  # noqa: E402
    tonometry_mapping,
    visual_acuity_mapping,
    colour_vision_mapping,
    body_fat_percentage_mapping,
    visceral_fat_mapping,
    spirometry_mapping,
    whr_mapping,
)
from repository.health_report.enums import TestTags  # noqa: E402


# ─── WHR calculation tests (via get_patient_measurement) ────────────────────

def test_whr_male_low_risk():
    """waist=85, hip=100 → WHR=0.85 → Male low risk (<0.90)"""
    rows = make_measurements(
        ("Waist Circumference", "85"),
        ("Hip Circumference", "100"),
    )
    result = get_patient_measurement("P001", rows)
    assert "SGiMed^WHR" in result, "WHR key missing"
    assert float(result["SGiMed^WHR"][0]) == 0.85
    print("✅  WHR male low risk: WHR=0.85 ✓")


def test_whr_male_moderate_risk():
    """waist=92, hip=100 → WHR=0.92 → moderate risk (0.90-0.99)"""
    rows = make_measurements(
        ("Waist Circumference", "92"),
        ("Hip Circumference", "100"),
    )
    result = get_patient_measurement("P002", rows)
    assert float(result["SGiMed^WHR"][0]) == 0.92
    print("✅  WHR male moderate risk: WHR=0.92 ✓")


def test_whr_male_high_risk():
    """waist=105, hip=100 → WHR=1.05 → high risk (≥1.0)"""
    rows = make_measurements(
        ("Waist Circumference", "105"),
        ("Hip Circumference", "100"),
    )
    result = get_patient_measurement("P003", rows)
    assert float(result["SGiMed^WHR"][0]) == 1.05
    print("✅  WHR male high risk: WHR=1.05 ✓")


def test_whr_female_low_risk():
    """waist=75, hip=100 → WHR=0.75 → female low risk (<0.80)"""
    rows = make_measurements(
        ("Waist Circumference", "75"),
        ("Hip Circumference", "100"),
    )
    result = get_patient_measurement("P004", rows)
    assert float(result["SGiMed^WHR"][0]) == 0.75
    print("✅  WHR female low risk: WHR=0.75 ✓")


def test_whr_female_high_risk():
    """waist=88, hip=100 → WHR=0.88 → female high risk (≥0.85)"""
    rows = make_measurements(
        ("Waist Circumference", "88"),
        ("Hip Circumference", "100"),
    )
    result = get_patient_measurement("P005", rows)
    assert float(result["SGiMed^WHR"][0]) == 0.88
    print("✅  WHR female high risk: WHR=0.88 ✓")


def test_whr_missing_hip():
    """Only waist present → WHR should NOT be calculated"""
    rows = make_measurements(("Waist Circumference", "85"))
    result = get_patient_measurement("P006", rows)
    assert "SGiMed^WHR" not in result
    print("✅  WHR with missing hip: no WHR key ✓")


def test_whr_zero_hip():
    """Hip=0 → division by zero protected"""
    rows = make_measurements(
        ("Waist Circumference", "85"),
        ("Hip Circumference", "0"),
    )
    result = get_patient_measurement("P007", rows)
    assert "SGiMed^WHR" not in result
    print("✅  WHR with hip=0: division guarded ✓")


# ─── WHR mapping (tag) tests ─────────────────────────────────────────────────

def _whr_meta(gender):
    return {
        "hl7_code": "SGiMed^WHR",
        "low_risk_writeup": None,
        "moderate_risk_writeup": "moderate",
        "high_risk_writeup": "high",
    }


def test_whr_mapping_male_low():
    results = {"SGiMed^WHR": ["0.85", "", None], "GENDER": ["M"]}
    r = whr_mapping(results, _whr_meta("M"))
    assert r.tag == TestTags.NORMAL
    print("✅  whr_mapping male 0.85 → NORMAL ✓")


def test_whr_mapping_male_moderate():
    results = {"SGiMed^WHR": ["0.92", "", None], "GENDER": ["M"]}
    r = whr_mapping(results, _whr_meta("M"))
    assert r.tag == TestTags.BORDERLINE
    assert r.writeup == "moderate_risk_writeup"
    print("✅  whr_mapping male 0.92 → BORDERLINE / moderate ✓")


def test_whr_mapping_male_high():
    results = {"SGiMed^WHR": ["1.05", "", None], "GENDER": ["M"]}
    r = whr_mapping(results, _whr_meta("M"))
    assert r.tag == TestTags.OUT_OF_RANGE
    assert r.writeup == "high_risk_writeup"
    print("✅  whr_mapping male 1.05 → OUT_OF_RANGE / high ✓")


def test_whr_mapping_female_low():
    results = {"SGiMed^WHR": ["0.75", "", None], "GENDER": ["F"]}
    r = whr_mapping(results, _whr_meta("F"))
    assert r.tag == TestTags.NORMAL
    print("✅  whr_mapping female 0.75 → NORMAL ✓")


def test_whr_mapping_female_moderate():
    results = {"SGiMed^WHR": ["0.82", "", None], "GENDER": ["F"]}
    r = whr_mapping(results, _whr_meta("F"))
    assert r.tag == TestTags.BORDERLINE
    assert r.writeup == "moderate_risk_writeup"
    print("✅  whr_mapping female 0.82 → BORDERLINE / moderate ✓")


def test_whr_mapping_female_high():
    results = {"SGiMed^WHR": ["0.88", "", None], "GENDER": ["F"]}
    r = whr_mapping(results, _whr_meta("F"))
    assert r.tag == TestTags.OUT_OF_RANGE
    assert r.writeup == "high_risk_writeup"
    print("✅  whr_mapping female 0.88 → OUT_OF_RANGE / high ✓")


# ─── Tonometry tests ─────────────────────────────────────────────────────────

def _tono_meta(eye="Right"):
    return {"hl7_code": f"SGiMed^IOP {eye}"}


def test_tonometry_normal():
    results = {"SGiMed^IOP Right": ["15", "mmHg", None]}
    r = tonometry_mapping(results, _tono_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Tonometry 15mmHg → NORMAL ✓")


def test_tonometry_low():
    results = {"SGiMed^IOP Right": ["8", "mmHg", None]}
    r = tonometry_mapping(results, _tono_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    assert r.writeup == "low_writeup"
    print("✅  Tonometry 8mmHg → OUT_OF_RANGE / low ✓")


def test_tonometry_high():
    results = {"SGiMed^IOP Right": ["25", "mmHg", None]}
    r = tonometry_mapping(results, _tono_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    assert r.writeup == "high_writeup"
    print("✅  Tonometry 25mmHg → OUT_OF_RANGE / high ✓")


# ─── Visual Acuity tests ─────────────────────────────────────────────────────

def _va_meta(eye="Right"):
    return {"hl7_code": f"SGiMed^Visual Acuity {eye}"}


def test_visual_acuity_normal_6_6():
    results = {"SGiMed^Visual Acuity Right": ["6/6", "", None]}
    r = visual_acuity_mapping(results, _va_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Visual Acuity 6/6 → NORMAL ✓")


def test_visual_acuity_normal_6_9():
    results = {"SGiMed^Visual Acuity Right": ["6/9", "", None]}
    r = visual_acuity_mapping(results, _va_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Visual Acuity 6/9 → NORMAL ✓")


def test_visual_acuity_abnormal():
    results = {"SGiMed^Visual Acuity Right": ["6/60", "", None]}
    r = visual_acuity_mapping(results, _va_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    print("✅  Visual Acuity 6/60 → OUT_OF_RANGE ✓")


# ─── Colour Vision tests ─────────────────────────────────────────────────────

def _cv_meta():
    return {"hl7_code": "SGiMed^Red-Green Deficiency"}


def test_colour_vision_no():
    results = {"SGiMed^Red-Green Deficiency": ["No", "", None]}
    r = colour_vision_mapping(results, _cv_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Colour Vision 'No' → NORMAL ✓")


def test_colour_vision_yes():
    results = {"SGiMed^Red-Green Deficiency": ["Yes", "", None]}
    r = colour_vision_mapping(results, _cv_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    print("✅  Colour Vision 'Yes' → OUT_OF_RANGE ✓")


def test_colour_vision_negative():
    results = {"SGiMed^Red-Green Deficiency": ["negative", "", None]}
    r = colour_vision_mapping(results, _cv_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Colour Vision 'negative' → NORMAL ✓")


def test_colour_vision_positive():
    results = {"SGiMed^Red-Green Deficiency": ["Positive", "", None]}
    r = colour_vision_mapping(results, _cv_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    print("✅  Colour Vision 'Positive' → OUT_OF_RANGE ✓")


# ─── Body Fat % tests ─────────────────────────────────────────────────────────

def _bf_meta():
    return {"hl7_code": "SGiMed^Total Body Fat Percentage"}


def test_body_fat_male_normal():
    results = {"SGiMed^Total Body Fat Percentage": ["20", "%", None], "GENDER": ["M"]}
    r = body_fat_percentage_mapping(results, _bf_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Body Fat male 20% → NORMAL ✓")


def test_body_fat_male_low():
    results = {"SGiMed^Total Body Fat Percentage": ["5", "%", None], "GENDER": ["M"]}
    r = body_fat_percentage_mapping(results, _bf_meta())
    assert r.tag == TestTags.OUT_OF_RANGE and r.writeup == "low_writeup"
    print("✅  Body Fat male 5% → OUT_OF_RANGE / low ✓")


def test_body_fat_male_high():
    results = {"SGiMed^Total Body Fat Percentage": ["30", "%", None], "GENDER": ["M"]}
    r = body_fat_percentage_mapping(results, _bf_meta())
    assert r.tag == TestTags.OUT_OF_RANGE and r.writeup == "high_writeup"
    print("✅  Body Fat male 30% → OUT_OF_RANGE / high ✓")


def test_body_fat_female_normal():
    results = {"SGiMed^Total Body Fat Percentage": ["28", "%", None], "GENDER": ["F"]}
    r = body_fat_percentage_mapping(results, _bf_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Body Fat female 28% → NORMAL ✓")


def test_body_fat_female_high():
    results = {"SGiMed^Total Body Fat Percentage": ["38", "%", None], "GENDER": ["F"]}
    r = body_fat_percentage_mapping(results, _bf_meta())
    assert r.tag == TestTags.OUT_OF_RANGE and r.writeup == "high_writeup"
    print("✅  Body Fat female 38% → OUT_OF_RANGE / high ✓")


# ─── Visceral Fat tests ───────────────────────────────────────────────────────

def _vf_meta():
    return {"hl7_code": "SGiMed^Visceral Fat Level"}


def test_visceral_fat_normal():
    results = {"SGiMed^Visceral Fat Level": ["8", "", None]}
    r = visceral_fat_mapping(results, _vf_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Visceral Fat 8 → NORMAL ✓")


def test_visceral_fat_high():
    results = {"SGiMed^Visceral Fat Level": ["12", "", None]}
    r = visceral_fat_mapping(results, _vf_meta())
    assert r.tag == TestTags.OUT_OF_RANGE and r.writeup == "high_writeup"
    print("✅  Visceral Fat 12 → OUT_OF_RANGE / high ✓")


def test_visceral_fat_very_high():
    results = {"SGiMed^Visceral Fat Level": ["16", "", None]}
    r = visceral_fat_mapping(results, _vf_meta())
    assert r.tag == TestTags.OUT_OF_RANGE and r.writeup == "very_high_writeup"
    print("✅  Visceral Fat 16 → OUT_OF_RANGE / very_high ✓")


# ─── Spirometry tests ─────────────────────────────────────────────────────────

def _sp_meta():
    return {"hl7_code": "SGiMed^Spirometry Result"}


def test_spirometry_normal():
    results = {"SGiMed^Spirometry Result": ["Normal", "", None]}
    r = spirometry_mapping(results, _sp_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Spirometry 'Normal' → NORMAL ✓")


def test_spirometry_restrictive():
    results = {"SGiMed^Spirometry Result": ["Restrictive", "", None]}
    r = spirometry_mapping(results, _sp_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    print("✅  Spirometry 'Restrictive' → OUT_OF_RANGE ✓")


def test_spirometry_obstructive():
    results = {"SGiMed^Spirometry Result": ["Obstructive", "", None]}
    r = spirometry_mapping(results, _sp_meta())
    assert r.tag == TestTags.OUT_OF_RANGE
    print("✅  Spirometry 'Obstructive' → OUT_OF_RANGE ✓")


def test_spirometry_case_insensitive():
    results = {"SGiMed^Spirometry Result": ["NORMAL", "", None]}
    r = spirometry_mapping(results, _sp_meta())
    assert r.tag == TestTags.NORMAL
    print("✅  Spirometry case-insensitive 'NORMAL' → NORMAL ✓")


# ─── get_patient_measurement extraction tests ─────────────────────────────────

def test_extraction_all_new_fields():
    """All new measurement types are extracted correctly."""
    rows = make_measurements(
        ("Waist Circumference", "85"),
        ("Hip Circumference", "100"),
        ("IOP Right", "15"),
        ("IOP Left", "14"),
        ("Visual Acuity Right", "6/6"),
        ("Visual Acuity Left", "6/9"),
        ("Red-Green Deficiency", "No"),
        ("Blue-Yellow Deficiency", "No"),
        ("Complete Colour Blindness", "No"),
        ("Total Body Fat Percentage", "22"),
        ("Visceral Fat Level", "8"),
        ("Spirometry Result", "Normal"),
    )
    result = get_patient_measurement("P999", rows)

    expected_keys = [
        "SGiMed^Waist Circumference",
        "SGiMed^Hip Circumference",
        "SGiMed^WHR",
        "SGiMed^IOP Right",
        "SGiMed^IOP Left",
        "SGiMed^Visual Acuity Right",
        "SGiMed^Visual Acuity Left",
        "SGiMed^Red-Green Deficiency",
        "SGiMed^Blue-Yellow Deficiency",
        "SGiMed^Complete Colour Blindness",
        "SGiMed^Total Body Fat Percentage",
        "SGiMed^Visceral Fat Level",
        "SGiMed^Spirometry Result",
    ]
    missing = [k for k in expected_keys if k not in result]
    assert not missing, f"Missing keys: {missing}"
    print(f"✅  All {len(expected_keys)} new measurement keys extracted ✓")
    print(f"     WHR auto-calculated: {result['SGiMed^WHR'][0]}")


# ─── Main runner ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # WHR calculation
        test_whr_male_low_risk,
        test_whr_male_moderate_risk,
        test_whr_male_high_risk,
        test_whr_female_low_risk,
        test_whr_female_high_risk,
        test_whr_missing_hip,
        test_whr_zero_hip,
        # WHR mapping
        test_whr_mapping_male_low,
        test_whr_mapping_male_moderate,
        test_whr_mapping_male_high,
        test_whr_mapping_female_low,
        test_whr_mapping_female_moderate,
        test_whr_mapping_female_high,
        # Tonometry
        test_tonometry_normal,
        test_tonometry_low,
        test_tonometry_high,
        # Visual Acuity
        test_visual_acuity_normal_6_6,
        test_visual_acuity_normal_6_9,
        test_visual_acuity_abnormal,
        # Colour Vision
        test_colour_vision_no,
        test_colour_vision_yes,
        test_colour_vision_negative,
        test_colour_vision_positive,
        # Body Fat
        test_body_fat_male_normal,
        test_body_fat_male_low,
        test_body_fat_male_high,
        test_body_fat_female_normal,
        test_body_fat_female_high,
        # Visceral Fat
        test_visceral_fat_normal,
        test_visceral_fat_high,
        test_visceral_fat_very_high,
        # Spirometry
        test_spirometry_normal,
        test_spirometry_restrictive,
        test_spirometry_obstructive,
        test_spirometry_case_insensitive,
        # Full extraction
        test_extraction_all_new_fields,
    ]

    passed = 0
    failed = 0
    print("\n" + "="*60)
    print("  Health Measurements Verification Tests")
    print("="*60 + "\n")

    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌  {t.__name__} FAILED: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)
    sys.exit(0 if failed == 0 else 1)
