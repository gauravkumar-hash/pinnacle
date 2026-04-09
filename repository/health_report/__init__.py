from .mapping import *
from .logic import *
from .enums import *

PROFILE_ICON_URL = 'https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/health_reports/icons/{}.png'

test_tag_mapping = {t.value.id: t.value for t in TestTags}

profile_tests_mapping = {
    p['profile'].value.id: p
    for p in health_report_profiles
}

tests_metadata_mapping = {
    x['test_code']: x
    for p in health_report_profiles
    for x in p['tests']
}