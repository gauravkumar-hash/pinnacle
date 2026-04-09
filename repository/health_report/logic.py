from pydantic import BaseModel
from .enums import TestTags

class TestConversionResult(BaseModel):
    tag: TestTags | None = None
    writeup: str | None = None

def cfloat(value, metadata):
    try:
        return float(value)
    except ValueError:
        if value[0] == '<':
            return float(value[1:]) - 0.01
        if value[0] == '>':
            return float(value[1:]) + 0.01
        if 'float_error' in metadata and value in metadata['float_error']:
            return float(metadata['float_error'][value])
        raise Exception(f"Error converting {metadata['test_code']}: '{value}' to float, Lab Range: {metadata['lab_range']}")

def test_generic_mapping(results, metadata):
    hl7_code = metadata['hl7_code']
    result, _, _ = results[hl7_code]
    lab_range = metadata['lab_range']

    # Gender-specific range
    if type(lab_range) == dict:
        lab_range = lab_range[results['GENDER'][0]]

    if lab_range is None:
        return TestConversionResult(tag=None)
    elif callable(lab_range):
        return lab_range(results, metadata)
    elif lab_range[:4] == '=Neg':
        result_is_zero = False
        try:
            result_is_zero = cfloat(result, metadata) == 0
        except Exception:
            pass
        if result == 'Neg' or result_is_zero: return TestConversionResult(tag=TestTags.NORMAL, writeup='negative_writeup')
        return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='positive_writeup')
    elif '-' in lab_range:
        low, high = lab_range.split('-')
        result = cfloat(result, metadata)
        low = float(low)
        high = float(high)
        if result < low: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='low_writeup')
        if result > high: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup')
        return TestConversionResult(tag=TestTags.NORMAL, writeup='in_range_writeup')
    elif lab_range[0] in ['=', '>', '<']:
        val = lab_range[1:].strip()
        if lab_range[0] == '=':
            if result.lower() == val.lower(): return TestConversionResult(tag=TestTags.NORMAL, writeup='in_range_writeup')
            else: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup')
        elif lab_range[1] == '=':
            result = cfloat(result, metadata)
            val = float(lab_range[2:].strip())
            if lab_range[0] == '>' and val > result: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='low_writeup')
            if lab_range[0] == '<' and val < result: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup')
            else: return TestConversionResult(tag=TestTags.NORMAL, writeup='in_range_writeup')
        else:
            result = cfloat(result, metadata)
            val = float(val)
            if lab_range[0] == '>' and val >= result: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='low_writeup')
            if lab_range[0] == '<' and val <= result: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup')
            else: return TestConversionResult(tag=TestTags.NORMAL, writeup='in_range_writeup')

