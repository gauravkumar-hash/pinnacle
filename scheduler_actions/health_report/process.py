import json
from tqdm import tqdm
from repository.health_report.mapping import health_report_profiles
from repository.health_report.logic import test_generic_mapping
from repository.health_report.enums import TestTags, ProfileReportResp, TestResult, ProfileHeader
from decimal import Decimal

def main():
    # Load test results
    with open('input/patient_measurements.json', 'r') as f:
        patient_measurements = json.load(f)
    with open('input/processed_reports.json', 'r') as f:
        processed_reports = json.load(f)

    patient_profiles = {}
    for report_id, patient_details in tqdm(processed_reports.items()):
        report_id = patient_details['report']['id']
        if report_id not in patient_measurements:
            print(f"{report_id}: No measurements found")
            continue

        test_results = patient_measurements[report_id]
        if 'PROFILE' not in test_results:
            print(f"{report_id}: No OBR test profile found")
            continue
        # print(f"{report_id}: Supported {test_results['PROFILE'][0]}")
        output = generate_profile_output(report_id, test_results)

        patient_profiles[report_id] = [json.loads(row.model_dump_json()) for row in output]

    with open('output/patient_profiles.json', 'w') as f:
        json.dump(patient_profiles, f, indent=4)

def remove_exponent(d):
    d = Decimal(d)
    return str(d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize())

# Function to generate the output for a profile
def generate_profile_output(report_id, test_results):
    profile_reports = []
    for health_report_profile in health_report_profiles:
        
        profile = health_report_profile['profile'].value
        mapped_results = []
        for test_props in health_report_profile['tests']:
            hl7_code = test_props['hl7_code']
            if hl7_code not in test_results:
                continue

            try:
                mapping_result = test_generic_mapping(test_results, metadata=test_props)
            except Exception as e:
                print(f"Error mapping {hl7_code}: {e}")
                continue

            test_value, unit, lab_range = test_results[hl7_code]
            title = test_props['test_code']
            if unit is None: unit = test_props.get('units', None)
            if lab_range is None: lab_range = test_props.get('lab_range', None)
            if type(lab_range) == dict:
                lab_range = lab_range[test_results['GENDER'][0]]
            if callable(lab_range): lab_range = None
            try:
                test_value = remove_exponent(test_value)
            except Exception:
                pass            
            if unit: test_value += f" {unit}"

            test_result = TestResult(
                test_code=title,
                value=test_value,
                desirable_range=lab_range,
                # LabRange(
                #     value=lab_range,
                #     image=test_props.get('desirable_range_image', None),
                #     image_ratio=test_props.get('desirable_range_image_ratio', None)
                # ),
                tag_id=mapping_result.tag.value.id if mapping_result and mapping_result.tag else None,
                messages=[mapping_result.writeup] if mapping_result and mapping_result.writeup else None
            )
            mapped_results.append(test_result)
        
        if len(mapped_results) == 0:
            continue

        category_tag = None
        if TestTags.OUT_OF_RANGE.value.id in [r.tag_id for r in mapped_results]:
            category_tag = TestTags.OUT_OF_RANGE
        elif TestTags.BORDERLINE.value.id in [r.tag_id for r in mapped_results]:
            category_tag = TestTags.BORDERLINE
        else:
            category_tag = TestTags.NORMAL

        profile_report = ProfileReportResp(
            profile_id=profile.id,
            overalls=[
                ProfileHeader(
                    tag_id=category_tag.value.id if category_tag else None,
                    messages=['description'],
                )
            ],
            results=mapped_results,
            lab_report_id=report_id
        )
        profile_reports.append(profile_report)

    return profile_reports

if __name__ == "__main__":
    main()
    
