from enum import Enum
from .logic import TestConversionResult, cfloat
from .enums import Profile, TestTags

def bp_mapping(results, metadata):
    Diastolic, Systolic = cfloat(results['SGiMed^Diastolic'][0], metadata), cfloat(results['SGiMed^Systolic'][0], metadata)
    if Diastolic < 40 or Systolic < 70: return TestConversionResult(tag=TestTags.OUT_OF_RANGE)
    if Diastolic < 60 and Systolic < 90: return TestConversionResult(tag=TestTags.OUT_OF_RANGE) # Borderline
    if Diastolic < 80 and Systolic < 120: return TestConversionResult(tag=TestTags.NORMAL)
    if Diastolic < 90 and Systolic < 140: return TestConversionResult(tag=TestTags.OUT_OF_RANGE) # Borderline
    if Diastolic < 100 and Systolic < 160: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup') # Borderline
    if Diastolic < 110 and Systolic < 180: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup')
    return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='high_writeup')

def liver_sgot_sgpt_mapping(results, metadata):    
    SGOT = cfloat(results['SGOT^SGOT (AST)'][0], metadata)
    normal_sgot = SGOT < 34
    tag = TestTags.OUT_OF_RANGE if not normal_sgot else TestTags.NORMAL
    if 'SGPT^SGPT (ALT)' not in results:
        return TestConversionResult(tag=tag)
    
    # Writeup is associated with SGPT
    SGPT = cfloat(results['SGPT^SGPT (ALT)'][0], metadata)    
    high_sgpt = SGPT > 49
    writeup = None
    if not normal_sgot and high_sgpt: writeup = 'high_writeup'
    return TestConversionResult(tag=tag, writeup=writeup)

def thyroid_tsh_mapping(results, metadata): 
    TSH = cfloat(results['11579-0 ^TSH^'][0], metadata)
    low_tsh = TSH < 0.55
    high_tsh = TSH > 4.78
    tag = TestTags.OUT_OF_RANGE if low_tsh or high_tsh else TestTags.NORMAL
    if '14920-3 ^Free T4^' not in results:
        return TestConversionResult(tag=tag)
    
    # Writeup is associated with Free T4
    FreeT4 = cfloat(results['14920-3 ^Free T4^'][0], metadata)
    writeup = None
    normal_freet4 = 11.5 <= FreeT4 <= 22.7
    if low_tsh and normal_freet4: writeup='low_writeup'
    if high_tsh and normal_freet4: writeup='high_writeup'
    return TestConversionResult(tag=tag, writeup=writeup)

def thyroid_freet4_mapping(results, metadata):
    TSH, FreeT4 = cfloat(results['11579-0 ^TSH^'][0], metadata), cfloat(results['14920-3 ^Free T4^'][0], metadata)
    # high_tsh_low_t4_writeup = metadata['low_writeup']['high_tsh']
    # normal_tsh_low_t4_writeup = metadata['low_writeup']['normal_tsh']
    # low_tsh_high_t4_writeup = metadata['high_writeup']
    
    # lab_range = '11.5-22.7'
    low_t4 = FreeT4 < 11.5
    high_t4 = FreeT4 > 22.7
    low_tsh = TSH < 0.55
    normal_tsh = 0.55 <= TSH <= 4.78
    high_tsh = TSH > 4.78
    
    writeup = None
    if (normal_tsh and low_t4): writeup ='normal_tsh_low_t4_writeup'
    if (high_tsh and low_t4): writeup ='high_tsh_low_t4_writeup'
    if (low_tsh and high_t4): writeup ='low_tsh_high_t4_writeup'
    tag = TestTags.OUT_OF_RANGE if low_t4 or high_t4 else TestTags.NORMAL
    return TestConversionResult(tag=tag, writeup=writeup)

def hpylori_mapping(results, metadata):
    hpylori = cfloat(results['17859-0 ^H. Pylori IgG Antibody^'][0], metadata)
    tag = TestTags.OUT_OF_RANGE if hpylori > 1.1 else TestTags.NORMAL
    writeup = 'negative_writeup' if hpylori < 0.9 else None
    writeup = 'positive_writeup' if hpylori > 1.1 else None
    return TestConversionResult(tag=tag, writeup=writeup)

def urine_epith_mapping(results, metadata):
    epith = results['EPITH^EPITH'][0]
    if '-' in epith:
        high = epith.split('-')[1]
        if float(high) > 50: return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='positive_writeup')
    
    return TestConversionResult(tag=TestTags.NORMAL, writeup='negative_writeup')

def urine_crystals_mapping(results, metadata):
    crystals = results['CRYSTAL AM^CRYSTAL AMT'][0]
    result_is_zero = False
    try:
        result_is_zero = float(crystals) == 0
    except Exception:
        pass
    if crystals == 'Neg' or result_is_zero: return TestConversionResult(tag=TestTags.NORMAL, writeup='negative_writeup')
    return TestConversionResult(tag=TestTags.OUT_OF_RANGE, writeup='positive_writeup')

class Profiles(Enum):
    CLINICAL_ASSESSMENT = Profile(id='clinical_assessment', title='Clinical Assessment')
    LIPID = Profile(id='lipid_panel', title='Lipid Profile')
    DIABETIC = Profile(id='diabetic_panel', title='Diabetic Mellitus Profile')
    LIVER = Profile(id='liver_panel', title='Liver Panel')
    RENAL = Profile(id='renal_profile', title='Kidney Profile')
    BONE_JOINT = Profile(id='bone_joint_profile', title='Bone & Joint Profile')
    HAEMETOLOGY = Profile(id='haematology', title='Haematology')
    THYROID = Profile(id='thyroid_function_test', title='Thyroid Function Test')
    HEPATITIS = Profile(id='hepatitis_profile', title='Hepatitis Profile')
    CARDIAC_RISK = Profile(id='cardiac_risk_panel', title='Cardiac Risk Panel')
    TUMOUR_MARKERS = Profile(id='tumour_markers', title='Tumor Marker Profile')
    STD = Profile(id='std_screen', title='STD Screen')
    ANAEMIA = Profile(id='anaemia_profile', title='Anaemia Profile')
    OTHERS = Profile(id='others', title='Others')
    URINE_ANALYSIS = Profile(id='urine_analysis', title='Urine Analysis')
    STOOL_ANALYSIS = Profile(id='stool_analysis', title='Stool Analysis')
    # HORMONE = Profile(id='hormonal_profile', title='Hormonal Profile')

profile_mapping = {p.value.id: p.value for p in Profiles}

health_report_profiles = [
    # Clinical Assessment
    {
        'profile': Profiles.CLINICAL_ASSESSMENT,
        'description': '',
        'tests': [
            {
                'test_code': 'Height',
                'hl7_code': 'SGiMed^Height',
                'lab_range': None,
                'low_writeup': None,
                'in_range_writeup': None,
                'high_writeup': None,
            },
            {
                'test_code': 'Weight',
                'hl7_code': 'SGiMed^Weight',
                'lab_range': None,
                'low_writeup': None,
                'in_range_writeup': None,
                'high_writeup': None,
            },
            {
                'test_code': 'Body Mass Index (BMI)',
                'hl7_code': 'SGiMed^BMI',
                'lab_range': '18.5-22.9',
                'low_writeup': '**Your Body Mass Index is lower than the recommended range.**\nYou should eat a healthy balanced diet. Overeating for the sake of gaining weight is not healthy. Regular exercise with muscle toning exercises are recommended.',
                'in_range_writeup': None,
                'high_writeup': '**Your Body Mass Index is higher than the recommended range.**\nNote that the risk of cardiovascular disease i.e. heart disease is increased for Asians with BMI greater than 23. You are advised to begin or continue regular aerobic exercises such as jogging, swimming, or brisk walking. Oily, fatty, and starchy foods should be avoided. Simple carbohydrates such as ice cream, chocolates, and sweets are high in calories and should also be reduced. A gradual weight loss of about 1 kg per week would be preferable.',
                'desirable_range_image': 'https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/health_reports/bmi_range.png',
                'desirable_range_image_ratio': 2.84
            },  
            {
                'test_code': 'Blood Pressure',
                'hl7_code': 'SGiMed^BP',
                'lab_range': bp_mapping,
                'low_writeup': None,
                'in_range_writeup': None,
                'high_writeup': '**Your Blood Pressure is not in the optimal range on the day of your health screening.**\nYou should monitor your blood pressure regularly and start lifestyle modifications as follows:\n(1)    Cut down on your salt intake (less than 2gm of sodium per day i.e. slightly less than a teaspoon of salt per day).\n(2)    Watch your weight (maintain your body mass index between 18.5 to 23).\n(3)    Stop smoking if you do smoke.\n(4)    Start regular exercise (aim for 2.5 hrs of aerobic exercises per week).\n(5)    Learn to cope with stress and to ensure adequate sleep.\n(6)    Reduce your cholesterol level if it is also elevated.\nIf your blood pressure does not reduce with lifestyle changes or if your blood pressure falls in the moderate or severe hypertension groups, you may require medication to control your blood pressure.',
                'desirable_range_image': 'https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/health_reports/bp_range.png',
                'desirable_range_image_ratio': 2.06
            },
        ]
    },
    
    # Lipid Profile
    {
        'profile': Profiles.LIPID,
        'description': 'A lipid profile is a complete cholesterol test that measures the amount of cholesterol and triglycerides in your blood.\n- LDL cholesterol is referred to as bad cholesterol because it can build up in the walls of your blood vessels. This increases your risk of coronary heart disease and atherosclerosis.\n- HDL cholesterol is good cholesterol because it removes excess cholesterol from your body.\n- High triglyceride levels can also increase your risk of cardiovascular (heart and blood vessel) disease.',
        'tests': [
            {
                'test_code': 'Total Cholesterol',
                'hl7_code': '14647-2 ^Total Cholesterol^',
                # [('Total Cholesterol', frow['Total Cholesterol'] > 5.1)],
                'lab_range': '< 5.2',
                'low_writeup': None,
                'high_writeup': '**Your Total Cholesterol level is high.**\nIncreased cholesterol may be the result of excess intake of cholesterol-laden foods. Prolonged hypercholesterolaemia results in progressive atherosclerosis where the blood vessels become narrowed and may become blocked causing stroke and heart attacks.',
            },
            {
                'test_code': 'HDL Cholesterol',
                'hl7_code': '14646-4 ^HDL-Cholesterol^',
                # [('HDL', frow['HDL-Cholesterol'] < 1)],
                'lab_range': '> 1.0',
                'low_writeup': '**Your HDL-Cholesterol level is low.**\nThis "good" cholesterol protects against atherosclerosis. It does so by removing cholesterol from our cells and transporting it to the liver for removal. You could raise it by ceasing to smoke (if you smoke), exercising regularly, and losing excess weight (if overweight). Pre-menopausal women typically have higher levels because of hormonal influence. You should have your lipid profile checked regularly.',
            },
            {
                'test_code': 'Total/HDL Cholesterol',
                'hl7_code': 'T/HDL^Total/HDL Ratio',
                'lab_range': '< 4.0',
                'low_writeup': None,
                'high_writeup': None,
            },
            {
                'test_code': 'LDL Cholesterol',
                'hl7_code': '39469-2 ^LDL-Cholesterol^',
                # [('LDL', frow['LDL-Cholesterol'] > 3.3)],
                'lab_range': '< 3.4',
                'float_error': { '*': '3.41', 'Reactive': '3.41', 'Non-reactive': '3.39' },
                'low_writeup': None,
                'high_writeup': '**Your LDL-Cholesterol level is high.**\nProlonged LDL-Hypercholesterolaemia results in progressive atherosclerosis where the blood vessels become narrowed and blocked causing possible stroke and heart attacks.',
            },
            
            {
                'test_code': 'Triglycerides',
                'hl7_code': 'TG^Triglycerides',
                # [('Triglycerides', frow['Triglycerides'] > 2.2)],
                'lab_range': '< 2.3',
                'low_writeup': None,
                'high_writeup': '**Your Triglyceride level is high.**\nYou should avoid oily, fatty, and fried food. Sugars and starches are high in caloric content and should also be curtailed. If you drink alcohol, this should be moderated. Regular graded exercises would be helpful especially if you are above your recommended body weight. Persistent hypertriglyceridemia increases the risk of vascular disease and medication is necessary if dietary curtailment is ineffective in reducing levels. Your triglyceride level should be tested on regular intervals.',
            },
        ],
    },
    
    # Diabetic Mellitus Profile
    {
        'profile': Profiles.DIABETIC,
        'description': 'A haemoglobin A1C (HbA1C) test is a blood test that shows what your average blood sugar level was over the past two to three months.',
        'tests': [
            {
                'test_code': 'Glucose',
                'hl7_code': '14771-0 ^Fasting Blood Glucose^',
                'lab_range': '3.6-6.1',
                'low_writeup': None,
                'high_writeup': '**Your Diabetes control is not optimal.**\nStrict dietary restriction, compliance to medication (if prescribed) and regular exercises are necessary to improve your diabetes control. Sub-optimal diabetes control will lead to development of complications over time e.g. heart diseases, eye diseases, kidney diseases etc. It is recommended that a HbA1C test be repeated in 3 months to assess the control. Introduction or modification of medication may be necessary if the control is still not optimal.',
            },
            {
                'test_code': 'HbA1c',
                'hl7_code': '17856-6 ^HbA1c^',
                'lab_range': '4.5-6.4',
                'float_error': { '.....': '0', '*': '0' },
                'low_writeup': None,
                'high_writeup': None,
            },
        ],
    },

    # Liver Panel
    {
        'profile': Profiles.LIVER,
        'description': '',
        'tests': [
            {
                'test_code': 'Total Bilirubin',
                'hl7_code': 'TB^Bilirubin (Total)',
                'lab_range': '5.0 - 21.0',
                'high_writeup': '**Your Bilirubin level is elevated.**\nBilirubin is the by-product of red blood cell degradation. It is excreted from the body via the liver. Isolated elevation of bilirubin level in the absence of other abnormality in the liver function test is possibly secondary to fasting or other conditions such as Gilbert\'s syndrome (a condition where the body has decrease excretion of bilirubin). A repeat liver function test under non-fasting state is recommended. Liver ultrasound scan will be a useful test for further evaluation of the liver status.',
            },
            {
                'test_code': 'Total Protein',
                'hl7_code': '2885-2  ^Total Protein^',
                'lab_range': '57-82',
                'low_writeup': '**Your Total Protein level is low.**\nThe total protein test measures the combined levels of albumin and globulin in the blood. It is a general marker of overall health and helps assess liver function, kidney function, and nutritional status. Low total protein in the blood may be due to liver disease, kidney disease, malnutrition or malabsorption, severe burns, bleeding or trauma.  Please consult the doctor for further advice.',
                'high_writeup': '**Your Total Protein level is high.**\nThe total protein test measures the combined levels of albumin and globulin in the blood. It is a general marker of overall health and helps assess liver function, kidney function, and nutritional status. High total protein may be due to chronic inflammation or infections, multiple myeloma, dehydration, autoimmune condition. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'Albumin',
                'hl7_code': '1751-7  ^Albumin^',
                'lab_range': '32-48',
                'low_writeup': '**Your Albumin level is low.**\nAlbumin is the most abundant protein in the blood, primarily produced by the liver. It plays a crucial role in maintaining fluid balance, transporting nutrients, and supporting immune function. Low albumin in the blood may be due to liver disease, kidney disease, malnutrition or malabsorption, severe  infections or inflammation.  Please consult the doctor for further advice.',
                'high_writeup': '**Your Albumin level is high.**\nAlbumin is the most abundant protein in the blood, primarily produced by the liver. It plays a crucial role in maintaining fluid balance, transporting nutrients, and supporting immune function. High albumin may be due to dehydration, high-protein diet. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'Globulin',
                'hl7_code': 'GLB^Globulin',
                'lab_range': '20-36',
                'low_writeup': '**Your Globulin level is low.**\nAlbumin is the most abundant protein in the blood, primarily produced by the liver. It plays a crucial role in maintaining fluid balance, transporting nutrients, and supporting immune function. Low albumin in the blood may be due to liver disease, kidney disease, malnutrition or malabsorption, severe  infections or inflammation.  Please consult the doctor for further advice.',
                'high_writeup': '**Your Globulin level is high.**\nGlobulins are a group of proteins in the blood that play essential roles in immune function, blood clotting, and nutrient transport. They include antibodies (immunoglobulins), transport proteins, and enzymes. High globulin maybe due to chronic infections, autoimmune diseases, liver disease, blood disorders or inflammatory conditions. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'A/G Ratio',
                'hl7_code': 'A/G^Albumin/Globulin Ratio',
                'lab_range': '1.2-2.5',
                'low_writeup': '**Your Albumin/Globulin Ratio (A/G Ratio) is low.**\nThe Albumin/Globulin (A/G) ratio compares the levels of albumin (produced by the liver) and globulin (which includes antibodies and transport proteins). It helps assess liver function, kidney health, immune system status, and nutritional balance. Low A/G ratio may be due to liver disease, kidney disease, chronic infection or inflammatory diseases, autoimmune diseases. Please consult the doctor for further advice.',
                'high_writeup': '**Your Albumin/Globulin Ratio (A/G Ratio) is high.**\nThe Albumin/Globulin (A/G) ratio compares the levels of albumin (produced by the liver) and globulin (which includes antibodies and transport proteins). It helps assess liver function, kidney health, immune system status, and nutritional balance. High A/G ratio may be due to malnutrition, malabsorption. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'AST/SGOT',
                'hl7_code': 'SGOT^SGOT (AST)',
                'lab_range': '<34',
                'low_writeup': None,
                'high_writeup': '**Your Liver Enzymes are elevated.**\nThis indicates liver inflammation. The cause may be dietary excess (e.g. high triglycerides level, diabetes, excessive alcohol intake), viral infection, such as hepatitis infection, or medication (e.g. traditional medication). You will need regular monitoring of your liver function. Further investigations and referral to a specialist will be needed if the enzyme levels are very high, or if the levels are increasing over time. Meanwhile, do abstain from alcoholic drink, smoking, and medications that are not prescribed by your doctor. Regular exercises and reducing unnecessary calories consumption are helpful.',
            },
            {
                'test_code': 'ALT/SGPT',
                'hl7_code': 'SGPT^SGPT (ALT)',
                'lab_range': '10-49',
                'low_writeup': None,
                'high_writeup': '**Your Liver Enzymes are elevated.**\nThis indicates liver inflammation. The cause may be dietary excess (e.g. high triglycerides level, diabetes, excessive alcohol intake), viral infection, such as hepatitis infection, or medication (e.g. traditional medication). You will need regular monitoring of your liver function. Further investigations and referral to a specialist will be needed if the enzyme levels are very high, or if the levels are increasing over time. Meanwhile, do abstain from alcoholic drink, smoking, and medications that are not prescribed by your doctor. Regular exercises and reducing unnecessary calories consumption are helpful.',
            },
            {
                'test_code': 'Alkaline Phosphatase',
                'hl7_code': '6768-6  ^Alkaline Phosphatase^',
                'lab_range': '46-116',
                'low_writeup': None,
                'high_writeup': '**Your Alkaline Phosphatase level is high.**\nAlkaline Phosphatase (ALP) is an enzyme found in various tissues, primarily in the liver, bones, kidneys, and intestines. It plays a key role in breaking down proteins and is an important marker in liver function and bone health screenings. High ALP levels may be due to liver disease, gallbladder disease, bone disorders, vitamin D deficiency or calcium metabolism diseases, hyperparathyroidism and pregnancy. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'Gamma GT',
                'hl7_code': '2324-2  ^GGT^',
                'lab_range': { 'M': '<= 73', 'F': '<= 38' },
                'low_writeup': None,
                'high_writeup': '**Your Gamma GT level is high.**\nGamma-Glutamyl Transferase (GGT) is an enzyme found in the liver, bile ducts, pancreas, and kidneys. It plays a role in detoxification and metabolism.  Raised GGT maybe due to alcohol consumption, consumption of certain medications, liver disease, obesity, diabetes. Please consult the doctor for further advice.',
            },
        ],
    },

    # Kidney Profile
    {
        'profile': Profiles.RENAL,
        'description': 'A renal panel is a group of tests that may be performed together to evaluate kidney (renal) function, to help diagnose kidney-related disorders, to screen those who may be at risk of developing kidney disease or to monitor individual who has been diagnosed with kidney disease. The tests measure levels of various substances, including several minerals, electrolytes and proteins in the blood to determine the current health of your kidneys.',
        'tests': [
            {
                'test_code': 'Urea',
                'hl7_code': '14937-7 ^Urea^',
                'lab_range': '2.5-6.6',
                'low_writeup': None,
                'high_writeup': '**Your Urea level is elevated.**\nUrea is produced in the liver as a way to dispose of excess nitrogen that comes from the breakdown of proteins. It is then transported in the blood to the kidneys and excreted in urine. Raised urea levels, can indicate various underlying conditions or situations like acute kidney injury, chronic kidney disease, or glomerulonephritis reduce the kidneys\' ability to filter urea, leading to its accumulation. Dehydration, Congestive heart failure, diet rich in protein or conditions that accelerate protein breakdown (such as severe infections, burns, or gastrointestinal bleeding) can increase urea production. Please consult the doctor for further instructions.',
            },
            {
                'test_code': 'Creatinine',
                'hl7_code': '14682-9 ^Creatinine^',
                'lab_range': { 'M': '62-115', 'F': '49-90' },
                'low_writeup': '**Your Creatinine level is low.**\nLow creatinine level will often result from a person having low muscle mass or body weight. However, low creatinine levels may also indicate a person has liver disease, is currently pregnant, or malnutrition. Please seek medical attention if you encounter any symptoms.',
                'high_writeup': '**Your Creatinine level is elevated.**\nMild elevation of creatinine can be a result of fasting. A repeat kidney function test under non-fasting state is recommended. If the creatinine level remains persistently high, a 24 hour creatinine clearance test is recommended to rule out kidney function impairment.',
            },
            {
                'test_code': 'e-GFR',
                'hl7_code': 'eGFR^e-GFR',
                'lab_range': '>=90',
                'low_writeup': '**Your eGFR level is low.**\nThe estimated glomerular filtration rate (eGFR) is a key measure of kidney function and it provides an estimate of how well your kidneys are filtering waste and excess fluid from your blood. Generally, an eGFR above 90 mL/min/1.73 m² is considered normal. It\'s important to note that eGFR naturally decreases with age, so slightly lower values in older adults might be acceptable. An eGFR between 60 and 89 mL/min/1.73 m² may indicate mild kidney function reduction, which might be normal for some individuals, particularly older adults. An eGFR below 60 mL/min/1.73 m², especially if persistent for three months or more, suggests chronic kidney disease (CKD) and warrants further evaluation and management.',
                'high_writeup': None,
            },
            {
                'test_code': 'Potassium',
                'hl7_code': '2823-3  ^Potassium^',
                'lab_range': '3.5-5.1',
                'float_error': { '*': '5.2' },
                'low_writeup': '**Your Potassium level is low.**\nPotassium is a critical electrolyte and it plays a key role in nerve function, muscle contraction, and maintaining heart rhythm. Hypokalemia (Low Potassium) may be due to drugs like loop and thiazide diuretics, vomiting or diarrhea and endocrine conditions like hyperaldosteronism (excess aldosterone). Please consult the doctor for further advice.',
                'high_writeup': '**Your Potassium level is elevated.**\nPotassium is a critical electrolyte and it plays a key role in nerve function, muscle contraction, and maintaining heart rhythm. Hyperkalemia (High Potassium) mya be due to reduced renal function, certain drugs like ACE inhibitors, ARBs and potassium sparing diuretics and metabolic conditions like metabolic acidosis. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'Sodium',
                'hl7_code': 'NA^Sodium',
                'lab_range': '136 - 145',
                'low_writeup': '**Your Sodium level is low.**\nSodium is a key electrolyte and it plays several vital roles in the body, including maintaining fluid balance, transmitting nerve impulses, and ensuring proper muscle function. Low Sodium (Hyponatremia) can be due to excessive fluid intake or water retention. (e.g., in heart failure, liver cirrhosis, or kidney disease) Other conditions like hormonal imbalances such as Syndrome of Inappropriate Antidiuretic Hormone Secretion (SIADH) and side effects from certain medications (e.g., diuretics, antidepressants). Please consult the doctor for further advice.',
                'high_writeup': '**Your Sodium level is elevated.**\nSodium is a key electrolyte and it plays several vital roles in the body, including maintaining fluid balance, transmitting nerve impulses, and ensuring proper muscle function. High Sodium (Hypernatremia)can be due to dehydration, excessive intake of sodium or underlying conditions like diabetes insipidus. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'Chloride',
                'hl7_code': 'CL^Chloride',
                'lab_range': '98-107',
                'low_writeup': None,
                'high_writeup': None,
            },
        ],
    },
    
    # Bone & Joint Profile
    {
        'profile': Profiles.BONE_JOINT,
        'description': 'A bone profile blood test, also known as a bone metabolism test or a bone turnover marker test, is a diagnostic tool used to assess various aspects of bone health and function. It is most often used to diagnose early signs of bone loss or osteoporosis.',
        'tests': [
            {
                'test_code': 'Calcium',
                'hl7_code': '2000-8  ^Calcium^',
                'lab_range': '2.08-2.65',
                'low_writeup': '**Your Calcium level is low.**\nLow level of calcium can be related to abnormal secretion and activity of parathyroid hormone. It can cause vague symptoms such as general weakness, abnormal bowel movements, abnormal sensations, and headaches. A repeat assessment is recommended. If the level is persistently low, a review with the endocrinologist is recommended.',
                'high_writeup': '**Your Calcium level is elevated.**\nElevated calcium level can be associated with hormone imbalance such as abnormal secretion of parathyroid hormone. It can also be related to increased albumin level. If the level is very high, it can cause symptoms such as anorexia, nausea, weakness etc. It is recommended that you do a repeat test with albumin level for assessment. If the result is persistently elevated, a detailed search for the actual cause should be done and this may require a review with an endocrinologist.',
            },
            {
                'test_code': 'Phosphate',
                'hl7_code': '14879-1 ^Phosphate^',
                'lab_range': '0.78-1.65',
                'low_writeup': '**Your Phosphate level is low.**\nThis can be a result of reduced intake. Dairy products are a good source of calcium and phosphate. Low fat milk and cheese can be taken. You are recommended to repeat the test for assessment to monitor the trend.',
                'high_writeup': 'A repeat assessment is recommended under non-fasting state.',
            },
            {
                'test_code': 'Uric Acid',
                'hl7_code': '14933-6 ^Uric Acid^',
                'lab_range': { 'M': '220-547', 'F': '184-464' },
                # 'lab_range': '184-464',
                'low_writeup': None,
                'high_writeup': '**Your Uric Acid is elevated.**\nHigh uric acid will increase your risk of developing gout where you only experience joint pain during gout attack or kidney stone disease. High uric acid may be due to a variety or combination of factors such as excess dietary intake, increased synthesis by the body (implying a genetic influence), reduced kidney excretion or drug exposure. You should reduce the intake of purine rich food such as shellfish (e.g. lobster, oysters, crayfish), internal organs (e.g. liver, entrails), ikan bilis, sardines and red meat (e.g. beef and mutton). Alcohol (e.g. beer, spirits and wine) should also be avoided. Beans, nuts, and related foods are rich in vegetable protein and intake should also be moderated. Daily fluid intake of 2 litres is recommended. Medication may be needed if you are symptomatic with evidence of kidney stone or gouty arthritis.',
            },
            {
                'test_code': 'Rheumatoid Factor (RF)',
                'hl7_code': 'RF^R A Factor',
                'lab_range': '<=14',
                'low_writeup': None,
                'high_writeup': 'Rheumatoid arthritis is a severe form of joint disease affecting mainly the joints of the hands and feet. Patients with rheumatoid arthritis may have high levels of rheumatoid arthritis factor and this may precede the onset of joints symptoms. If you are asymptomatic, a follow up assessment with rheumatoid arthritis factor titre is recommended. If you already experience joint pain and swelling, a review with a rheumatologist is recommended.',
            }
        ],
    },

    # Haematology Profile
    {
        'profile': Profiles.HAEMETOLOGY,
        'description': 'A haematology profile is a blood test that measures the size and important characteristics of each circulating blood cell. This test can help detect conditions such as anaemia, infection, inflammation, or leukaemia.',
        'tests': [
            {
                'test_code': 'WBC',
                'hl7_code': 'TWBC^WBC',
                'lab_range': '4.0-11.0',
                'float_error': { '*': '0' },
                'low_writeup': '**Your White Blood Cell Count is low.**\n This is suggestive of recent viral infection. Recommend follow up assessment if symptomatic.',
                'in_range_writeup': None,
                'high_writeup': '**Your White Blood Cell Count is high.**\nA raised white blood cell (WBC) count in a health screening could indicate a variety of conditions, ranging from mild infections to more serious health concerns. The significance of an elevated WBC count depends on how high it is, any accompanying symptoms, and other test results. Please consult the doctor for further instructions.',
            },
            {
                'test_code': 'RBC',
                'hl7_code': 'TRBC^RBC',
                'lab_range': '3.8-5.4',
                'float_error': { '*': '0' }
            },
            {
                'test_code': 'Haemoglobin',
                'hl7_code': '718-7   ^Haemoglobin^',
                # 'lab_range': { 'M': '13.5-18.0', 'F': '11.5-16.0' },
                'lab_range': '11.5-16.0',
                'float_error': { '*': '0' },
                'low_writeup': '**Your Haemoglobin level is low.**\n Anaemia may be due to a variety or combination of reasons. Commonly, it is due to a lack of blood forming elements like iron and folic acid. Diagnostic tests are available to detect common dietary deficiencies. Dietary supplements may be required in these cases. Anaemia can also be due to hereditary reasons, e.g. Thalassaemia. This means that you may have certain genes that cause production of defective haemoglobin. Individuals with such inherited anaemias are usually asymptomatic and well although they may transmit the condition to their offspring. Haemoglobin electrophoresis will be useful as screening test.',
            },
            {
                'test_code': 'PCV',
                'hl7_code': 'PCV^PCV (HCT)',
                'lab_range': { 'M': '38.0-52.0', 'F': '36.0-46.0' },
                'float_error': { '*': '0' },
            },
            {
                'test_code': 'Platelets',
                'hl7_code': 'PLT^Platelets',
                'lab_range': '150-400',
                'float_error': { '*': '0' },
                'low_writeup': '**Your Platelet Count is low.**\nA platelet count of less than 150,000 platelets per microliter is lower than normal. When you have a low platelet count, you may have trouble stopping bleeding. Bleeding can happen inside your body, underneath your skin, or from the surface of your skin.',
                'in_range_writeup': None,
                'high_writeup':	'**Your Platelet Count is elevated.**\nThis is possibly due to haemoconcentration secondary to fasting. You may want to repeat a non-fasting blood count for assessment.',
            },
            {
                'test_code': 'ESR',
                'hl7_code': '30341-2 ^ESR^',
                # 'lab_range': { 'M': '0-10', 'F': '0-20' },
                'lab_range': '0-20',
                'float_error': { '*': '0' },
                'low_writeup': None,
                'in_range_writeup': None,
                'high_writeup': '**Your Elevated Erythrocyte Sedimentation rate (ESR) is elevated.**\nThe ESR is a measure of inflammatory activity in the body. Minor elevation is usually due to infections such as flu or minor inflammation such as sprains or aging. Higher elevation is indicative of more serious and inflammatory conditions such as chronic infections (such as tuberculosis), joint problems (such as osteoarthritis, rheumatoid arthritis), blood disorders or more sinister disease. Follow up assessment is recommended to monitor the trend. If it is raised persistently, further investigations would be needed to determine the cause.',
            }
        ],
    },
    
    # Thyroid Function Test
    {
        'profile': Profiles.THYROID,
        'description': 'A Thyroid function test (TFT) commonly refers to the quantitation of thyroid stimulating hormone (TSH) and circulating thyroid hormones in serum to assess the ability of the thyroid gland to produce and regulate thyroid hormone production. It is used to diagnose hyperthyroidism (too much thyroid hormone) or hypothyroidism (too little thyroid hormone) in your blood.',
        'tests': [
            {
                'test_code': 'TSH',
                'hl7_code': '11579-0 ^TSH^',
                'lab_range': thyroid_tsh_mapping,
                'low_writeup': '**Low TSH and normal T4 level were noted in your screening.**\nThis is suggestive of subclinical hyperthyroidism. The thyroid gland modulates the metabolic processes of the body through a hormone called thyroxine. Hyperthyroidism is the result of excess thyroxine secretions. It causes symptoms such as weight loss despite an increased appetite, a preference for cool environments, anxiety, tremors, sweating and general irritability. Causes may be gland dysfunction, infection, drug exposure or malignancy.\nYour results suggested possible early hyperthyroidism. Recommend to repeat full thyroid function for monitoring the trend.',
                'high_writeup': '**Increased TSH and normal T4 level were noted in your screening.**\nThis is suggestive of subclinical hypothyroidism. The thyroid gland modulates the metabolic processes of the body through a hormone called thyroxine. Hypothyroidism is due to reduced levels of thyroxine resulting in mental and physical lethargy and weight gain due to slowing of metabolic rate. The cause may be gland failure, infection, drug suppression or malignancy.\nYour results suggested possible early hypothyroidism. Recommend to repeat full thyroid function for monitoring the trend.',
            },
            {
                'test_code': 'Free T4',
                'hl7_code': '14920-3 ^Free T4^',
                'lab_range': thyroid_freet4_mapping,
                'low_writeup': {
                    'normal_tsh': 'Your results for the thyroid screening are inconclusive, it is advisable to repeat the test in 6-8 weeks.',
                    'high_tsh': "**Your Thyroid screening is suggestive of hypothyroidism.**\nThe thyroid gland modulates the metabolic processes of the body through a hormone called thyroxine. Hypothyroidism is due to reduced levels of thyroxine resulting in mental and physical lethargy and weight gain due to slowing of metabolic rate. The cause may be gland failure, infection, drug suppression or malignancy. Thyroxine replacement may be needed. Follow up and treatment by a doctor is advisable.",
                },
                'high_writeup': '**Your Thyroid screening is suggestive of hyperthyroidism.**\nThe thyroid gland modulates the metabolic processes of the body through a hormone called thyroxine. Hyperthyroidism is the result of excess thyroxine secretions. It causes symptoms such as weight loss despite an increased appetite, a preference for cool environments, anxiety, tremors, sweating and general irritability. Causes may be gland dysfunction, infection, drug exposure or malignancy. You should be treated and follow up by a doctor.',
            }
        ],
    },

    # Hepatitis Profile
    {
        'profile': Profiles.HEPATITIS,
        'description': 'Hepatitis is an inflammation of the liver caused by a virus. The hepatitis profile includes tests for hepatitis B and hepatitis C.',
        'tests': [
            # # TODO: Missing Hepatitis HL7 codes
            # {
            #     'test_code': 'Hepatitis Bs Antigen',
            #     'hl7_code': None,
            #     'lab_range': '=Neg',
            #     'negative_writeup': None,
            #     'positive_writeup': '**You are noted to be a Hepatitis B carrier.**\nHepatitis B is an infection of the liver by a virus that is transmitted through contact with infected body fluids such as during delivery, via unprotected sex, accidental needle prick injuries or transfusion with contaminated blood products. You were found to be a carrier for the hepatitis B virus. A carrier status increases your risk of getting liver problems such as liver failure or liver cancer. You are advised to do 3 - 6 monthly assessment with liver function test and alpha-foeto protein level. Ultrasound examination is recommended to be done annually or when abnormality is detected on the 6 monthly blood surveillance. Assessment of hepatitis B e-antigen and antibody status are useful, to determine whether you have replicative infection. Your family members should also be screened for hepatitis B. They should be vaccinated if they are found not to be carriers.',
            # },
            # {
            #     'test_code': 'Hepatitis Bs Antibody',
            #     'hl7_code': None,
            #     'lab_range': '10-??', # TODO: This require three ranges out_of_range, in_range (low, normal)
            #     'negative_writeup': '**You are not protected against Hepatitis B infection.**\nHepatitis B is an infection of the liver by a virus that is transmitted through contact with infected body fluids such as during delivery, via unprotected sex, accidental needle prick injuries or transfusion with contaminated blood products. Immunisation with hepatitis B vaccine is available. The primary immunisation consists of 3 injections of vaccines over a 6-month period. Boosters are then required about once every 5 to 10 years to maintain adequate immunity.',
            #     'low_writeup': '**You are protected against Hepatitis B infection, but your immunity level is low.**\nHepatitis B is an infection of the liver by a virus that is transmitted through contact with infected body fluids such as during delivery, via unprotected sex, accidental needle prick injuries or transfusion with contaminated blood products. An antibody level above 10 is protective against hepatitis B infection. Your antibody level is adequate, but the level can be boosted with a booster vaccination to increase the duration of its protection.',
            #     'positive_writeup': '**You are protected against Hepatitis B infection.**\nThere is immunity agaisnt Hepatitis B and no further action is needed.',
            # },
            # {
            #     'test_code': 'Hepatitis A Total Antibody',
            #     'hl7_code': None,
            #     'lab_range': '=Neg',
            #     'negative_writeup': '**There is no evidence that you are protected against Hepatitis A infection.**\nHepatitis A is an infection of the liver by a virus that is transmitted by infected food or drink, it is commonly found in poorly cooked seafood and food prepared under poor hygienic conditions. There is no immunity against Hepatitis A detected. Please consider vaccination.',
            #     'positive_writeup': '**You are protected against Hepatitis A infection.**\nThere is immunity from past infection or vaccination and no further action is needed.'
            # },
            # {
            #     'test_code': 'Hepatitis C',
            #     'hl7_code': 'Hepatitis C',
            #     'lab_range': '=Neg',
            #     'negative_writeup': None,
            #     'positive_writeup': '**Your Hepatitis C serology was positive.**\nHCV antibodies detected (past or current infection), please consult the doctor for further instructions as you may need confirmation with HCV RNA test to check for active infection.',
            # }
        ],
    },
    
    # Cardiac Risk Profile
    {
        'profile': Profiles.CARDIAC_RISK,
        'description': 'Cardiac blood tests help to determine whether there has been any cardiac tissue damage and assess your risk of getting heart and blood vessel diseases. An abnormal value of these blood tests may indicate your heart is unhealthy.',
        'tests': [
            {
                'test_code': 'Hs C-Reactive Protein (HsCRP)',
                'hl7_code': 'HSCRP^hs-CRP',
                'lab_range': '<= 3.0',
                'low_writeup': None,
                'high_writeup': '**Your hs-CRP level is elevated.**\nC-reactive protein is an acute phase protein indicating presence of inflammation. The ability to measure C-reactive protein at very low concentrations may permit identification of asymptomatic patients at risk of acute coronary events. Levels above 3 mg/L should be rechecked in 2 weeks. Persistently elevated levels may indicate higher coronary risk in the absence of any concurrent infection or inflammation.',
            },
            {
                'test_code': 'Apolipoprotein A1',
                'hl7_code': '1869-7  ^Apolipoprotein A1^',
                'lab_range': { 'M': '79-169', 'F': '76-214' },
                'low_writeup': '**Your Apolipoprotein A level is low.**\nApolipoprotein A (ApoA) is the major lipoprotein in HDL cholesterol, the "good cholesterol." It plays a crucial role in cholesterol transport and removal, helping to reduce the risk of cardiovascular disease (CVD). Low ApoA maybe due to obesity, metabolic syndrome, diabetes, smoking, excessive alcohol consumption, inflammatory conditions. Please consult the doctor for further advice.',
                'high_writeup': '**Your Apolipoprotein A level is high.**\nApolipoprotein A (ApoA) is a key protein component of high-density lipoprotein (HDL), the "good cholesterol." It plays a crucial role in cholesterol transport and removal, helping to reduce the risk of cardiovascular disease (CVD). High ApoA maybe due to regular exercise, healthy diet rich in unsaturated fats.',
            },
            {
                'test_code': 'Apolipoprotein B',
                'hl7_code': '1884-6  ^Apolipoprotein B^',
                'lab_range': { 'M': '46-174', 'F': '46-142' },
                'low_writeup': None,
                'high_writeup': '**Your Apolipoprotein B level is high.**\nApolipoprotein B (ApoB) is the primary protein in low-density lipoprotein (LDL), often referred to as "bad cholesterol." High ApoB maybe due to obesity, diabetes, unhealthy diet. Please consult the doctor for further advice.',
            },
            # {
            #     'test_code': 'Apolipoprotein A1/B Ratio',
            #     'hl7_code': '13462-7 ^Apo A1/Apo B Ratio^',
            #     'lab_range': None, # TODO: Missing Apo A1/B Ratio
            #     'low_writeup': None,
            #     'high_writeup': '**Your Apolipoprotein B/Apolipoprotein A1 Ratio is high.**\nThe ApoB/ApoA1 ratio is a valuable marker in cardiovascular risk assessment. It compares atherogenic (plaque-forming) lipoproteins (ApoB) to anti-atherogenic (protective) lipoproteins (ApoA1). High Apolipoprotein B/Apolipoprotein A1 Ratio (ApoB/ApoA1) maybe due to obesity, metabolic syndrome, diabetes, smoking, excessive alcohol consumption, sedentary lifestyle. Please consult the doctor for further instructions.',
            # }
        ],
    },
    
    # Tumor Marker Profile
    {
        'profile': Profiles.TUMOUR_MARKERS,
        'description': 'Tumour markers can indicate the presence of certain types of cancers. **Note:** The presence of tumour markers alone is not enough to diagnose cancer. The blood tests are often not specific for cancer and may not be sensitive enough to pick up a cancer recurrence. You will probably need other tests to learn more about a possible cancer or recurrence.',
        'tests': [
            {
                'test_code': 'Liver: Alpha Fetoprotein (AFP)',
                'hl7_code': '1834-1  ^Alpha Fetoprotein^',
                'lab_range': '< 8.1',
                'low_writeup': None,
                'high_writeup': '**Your Alpha-Fetoprotein (α-FP) level is elevated.**\nYour screening shows an elevation of Alpha-Fetoprotein level. High levels of AFP may be an indicator of cancer of the liver, ovaries, or testicles. However, having a high AFP level does not mean you have cancer or that you will get cancer. Liver injury and liver diseases that are not cancer can also cause high AFP levels. Less often, high levels of AFP may be a sign of other cancers, including lymphoma or lung cancer. A doctor will use your medical history and other test results to make a diagnosis.  High levels are also seen in normal pregnant women. Levels that are much higher than expected for the period of pregnancy may suggest fetal abnormalities. Repeat measurement and ultrasound of the abdomen are recommended. Specialist review may be necessary, especially if the level is markedly elevated.',
            },
            {
                'test_code': 'Colon: Carcinoembryonic Antigen (CEA)',
                'hl7_code': '2039-6  ^CEA^',
                'lab_range': '<= 5.0',
                'low_writeup': None,
                'high_writeup': '**Your Carcinoembryonic Antigen (CEA) level is elevated.**\nYour screening shows an elevation of CEA level. CEA is a tumour marker, and it can be raised in colorectal cancer and to a lesser extent malignancies involving the breasts, lung, prostate, pancreas and ovary. Mild elevation of CEA level has also been found in smokers. Repeat measurement is advised. Specialist review may be necessary if the CEA is markedly elevated, if it is associated with positive stool occult blood test, or if there is a history of changes in bowel habits.',
            },
            {
                'test_code': 'Pancreas: CA 19.9',
                'hl7_code': 'CA199^CA 19.9',
                'lab_range': '<= 37.0',
                'low_writeup': None,
                'high_writeup': '**Your CA 19-9 (Carbohydrate Antigen 19-9) level is elevated.**\nCA 19-9 (Carbohydrate Antigen 19-9) is a tumor marker primarily used to aid in the diagnosis and monitoring of pancreatic cancer and other malignancies, such as bile duct, gallbladder, and gastrointestinal cancers. It can also be elevated in benign conditions such as pancreatitis, liver disease, and obstructive jaundice. It can also be raised in conditions like pancreatic cancer or cholangiocarcinoma. Please consult the doctor for further instructions.',
            },
            {
                'test_code': 'Ovary: CA 125 (F)',
                'hl7_code': 'CA125^CA 125',
                'lab_range': '<= 35.0',
                'low_writeup': None,
                'high_writeup': '**Your CA-125 level is elevated.**\nYour screening shows an increase of CA-125 level. CA-125 is tumour marker, and high level of CA-125 may be an indicator of cancers of the female genital-reproductive organs and to a lesser extent, other malignancies.  The CA-125 test is not used alone to diagnose ovarian cancer. Pelvic ultrasound assessment is recommended and if it is normal, repeat CA-125 testing should be carried out for review. A gynaecologist consult may be necessary if there is abnormality in the pelvic scan or if the CA-125 level is persistently elevated.',
            },
            {
                'test_code': 'Breast: CA 15.3 (F)',
                'hl7_code': 'CA153^CA 15.3',
                'lab_range': '<= 32.4',
                'low_writeup': None,
                'high_writeup': '**Your CA15.3 level is elevated.**\nYour screening shows an increase of CA 15.3 level. CA 15.3 is tumour marker, and it may be raised in benign breast disease and in particular breast cancer. Breast ultrasound and / or mammogream assessment is recommended and if it is normal, repeat Ca 15.3 testing should be carried out for review. A consult with a breast surgeon may be necessary if there is abnormality in the breast ultrasound scan or mammogram or if the level is persistently elevated.',
            },
            {
                'test_code': 'Prostate: PSA (M)',
                'hl7_code': '2857-1  ^Total PSA^',
                'lab_range': '<= 4.0',
                'low_writeup': None,
                'high_writeup': '**Your Prostate Specific Antigen (PSA) level is elevated.**\nYour screening showed an increase in prostate specific antigen level. High level of PSA may be an indicator of prostatic diseases such as benign prostatic hypertrophy, prostatitis, and prostate cancer. Repeat measurement and a prostate ultrasound are useful investigations as a follow up. A urologist review may be necessary if the ultrasound scan is abnormal, the PSA level is very high, there is persistent elevation of PSA, or there are symptoms with poor urine flow and frequency of urination.',
            },
            {
                'test_code': 'Nose: EBV',
                'hl7_code': 'EBV^EBV EA+EBNA-1 IgA',
                'lab_range': '< 8.0',
                'low_writeup': None,
                'high_writeup': '**Your Anti-EBV VCA level is elevated.**\nAnti EBV VCA and Ea / lgA levels are tumour markers associated with nasopharyngeal cancers. There was borderline reactivity of your anti EBV VCA / lgA level. Symptoms and signs of nasopharyngeal cancer are unexplained frequent nose bleeding, swollen lymph nodes, especially in the neck area, persistent ringing sound in the ear or unexplained hearing loss. If any of the aforementioned symptoms are noted, an Ear, Nose and Throat specialist review is strongly recommended.',
            }
        ],
    },

    # STD Screen
    {
        'profile': Profiles.STD,
        'description': None,
        'tests': [
            {
                'test_code': 'VDRL',
                'hl7_code': '31147-2 ^VDRL.^',
                'lab_range': None,
                'low_writeup': None,
                'high_writeup': None,
            },
            # {
            #     'test_code': 'TPHA',
            #     'hl7_code': None, # TODO: Missing TPHA HL7 code
            #     'lab_range': None,
            #     'negative_writeup': '**False positive VDRL result was noted.**\nYour VDRL serology for screening of syphilis was positive but confirmatory TPHA serology was negative. This means that you have a false positive result. Acute or chronic infections by other organisms as well as some chronic inflammatory disease states may cause a false positive VDRL result.',
            #     'positive_writeup': '**VDRL and TPHA tests for the screening of syphilis were positive in your blood investigations.**\nSpecialist referral and follow up is necessary for the management of syphilis.',
            # }
        ],
    },

    # Anaemia Profile
    {
        'profile': Profiles.ANAEMIA,
        'description': None,
        'tests': [
            {
                'test_code': 'Iron',
                'hl7_code': 'IRON^Iron',
                'lab_range': { 'M': '12-31', 'F': '9-30' },
            },
            {
                'test_code': 'Total Iron Binding Capacity (TIBC)',
                'hl7_code': 'TIBC^TIBC',
                'lab_range': '45-76',
            },
            {
                'test_code': '% Iron Saturation',
                'hl7_code': 'SAT^% Iron Saturation',
                'lab_range': { 'M': "25-56", 'F': "14-51" },
                'low_writeup': '**Your iron saturation level is low.**\nAn iron profile is a set of blood tests used to assess the body\'s iron levels and storage. Low iron saturation may be due to iron deficiency due to inadequate dietary iron intake, chronic blood loss like heavy menstrual bleeding or gastrointestinal bleeding or malabsorption issues like celiac disease. Please consult the doctor for further advice.',
                'high_writeup': '**Your iron saturation level is elevated.**\nAn iron profile is a set of blood tests used to assess the body\'s iron levels and storage. High iron saturation may be due to hereditary hemochromatosis which is a genetic disorder causes increased intestinal iron absorption, often leading to high iron saturation along with elevated serum iron and ferritin levels. It can also be due to excessive iron intake from repeated blood transfusion or overuse of iron supplements. Please consult the doctor for further advice.',
            },
            {
                'test_code': 'Ferritin',
                'hl7_code': '14723-1 ^Ferritin^',
                'lab_range': { 'M': "48-708", 'F': "22-640" },
                'low_writeup': "**Your ferritin level is low.**\nFerritin acts as a marker of the body\'s iron stores. Low ferritin typically is due to iron deficiency. Please consult the doctor for further advice.",
                'high_writeup': "**Your ferritin level is high.**\nFerritin acts as a marker of the body\'s iron stores. High ferritin may indicate iron overload or an inflammatory state. Please consult the doctor for further advice.",
            },
            {
                'test_code': 'Transferrin',
                'hl7_code': '3034-6  ^Transferrin^',
                'lab_range': { 'M': "2.15-3.65", 'F': "2.50-3.80" },
                'low_writeup': None,
                'high_writeup': None,
            },
            {
                'test_code': 'Folate',
                'hl7_code': '14732-2 ^Folic Acid.^',
                'lab_range': '> 12.2',
                'low_writeup': "**Your folate level is low.**\nFolate, also known as vitamin B9, is an essential nutrient that plays a critical role in cell division, DNA synthesis, and the formation of red blood cells. Low folate may be due to inadequate dietary intake (e.g., insufficient consumption of leafy greens, legumes, or fortified foods). It may be also due to Malabsorption issues (such as celiac disease) or certain medications that interfere with folate absorption or metabolism (e.g., methotrexate, some anticonvulsants). Please consult the doctor for further advice.",
                'high_writeup': None,
            },
            {
                'test_code': 'Vitamin B12',
                'hl7_code': '14685-2 ^Vitamin B12.^',
                'lab_range': "156-672",
                'low_writeup': "**Your vitamin B12 level is low.**\nLow vitamin B12 levels may be due to dietary insufficiency more common in vegetarians or vegans who do not consume enough animal products, which are primary sources of B12. It may be due to malabsorption conditions like pernicious anaemia, celiac disease, Crohn\'s disease, or after certain gastrointestinal surgeries can impair absorption. Please consult the doctor for further advice.",
                'high_writeup': None,
            }
        ],
    },

    # Others
    {
        'profile': Profiles.OTHERS,
        'description': None,
        'tests': [
            {
                'test_code': 'Total Vitamin D',
                'hl7_code': '62292-8 ^Total 25 (OH) Vitamin D^',
                'lab_range': '30-100',
                'low_writeup': "**Your Vitamin D level is low.**\nVitamin D is an essential nutrient that plays a vital role in maintaining bone health, supporting the immune system, and modulating inflammation. Low vitamin D levels maybe due to limited sun exposure, which reduces skin synthesis of vitamin D, poor dietary intake or malabsorption issues, such as in celiac disease or inflammatory bowel disease. Please consult the doctor for further advice.",
                'high_writeup': None,
            },
            {
                'test_code': 'H Pylori IgG',
                'hl7_code': '17859-0 ^H. Pylori IgG Antibody^',
                'lab_range': hpylori_mapping,
                'float_error': { '*': 1.11, 'Reactive': 1.11, 'Non-reactive': 1.09, 'Negative': 0.8 },
                'negative_writeup': '**Negative H.pylori IgG is detected**\nH. pylori IgG is a blood test that detects antibodies against H. pylori, a bacterium that infects the stomach lining and is a major cause of gastritis, peptic ulcers, and stomach cancer. Negative results means there is no exposure to H. pylori before.',
                'low_writeup': None,
                'positive_writeup': '**Positive H.pylori IgG is detected**\nH. pylori IgG is a blood test that detects antibodies against H. pylori, a bacterium that infects the stomach lining and is a major cause of gastritis, peptic ulcers, and stomach cancer. A positive result does not confirm an active infection—it only indicates past exposure. Please consult the doctor for further advice.',
                'high_writeup': None,
            }
        ],
    },

    # Urine Analysis
    {
        'profile': Profiles.URINE_ANALYSIS,
        'description': 'A urine analysis involves checking the appearance, concentration and content of urine. It is used to detect and manage a wide range of disorders, such as urinary tract infections (UTIs), kidney disease and diabetes.',
        'tests': [
            {
                'test_code': 'Protein',
                'hl7_code': '2888-6  ^Urine Protein (24 Hr)^',
                'lab_range': '0-150', # TODO: Need more values to validate what is the range
                'float_error': { '.....': 150.1 },
                'low_writeup': None,
                'high_writeup': '**Presence of Protein.**\nUnder normal circumstances, protein should not be found in a urine specimen. A repeat urine sample first thing in the morning should be collected for assessment to rule out orthostatic proteinuria (a benign condition where proteinuria is associated with upright posture). Persistent protein in the urine (i.e. presence of protein in two first morning urine tests separated by 1 week) may indicate the presence of kidney disorders and should be investigated.',
            },
            {
                'test_code': 'Ketones',
                'hl7_code': 'KETONE^KETONE',
                'lab_range': '=Neg',
                'negative_writeup': None,
                'positive_writeup': '**Presence of Ketones.**\nKetones are present in the urine of persons after fasting or patients with poorly controlled diabetes mellitus. Repeat midstream sampling after adequate hydration is suggested.',
            },
            {
                'test_code': 'Nitrite',
                'hl7_code': 'NITRITE^NITRITE',
                'lab_range': '=Neg',
                'negative_writeup': None,
                'positive_writeup': '**Presence of Nitrite.**\nYour urinalysis suggests presence of nitrite in your urine. This could be due to kidney or urinary tract infection. Treatment may be needed if you experience symptoms such as painful and/or frequent urination. A repeat test on a midstream specimen of urine is advisable.',
            },
            {
                'test_code': 'WBC',
                'hl7_code': 'WBC^WBC',
                'lab_range': '=Neg',
                'negative_writeup': None,
                'positive_writeup': '**Presence of Pyuria.**\nYour urinalysis suggests an excess amount of white cells in your urine. This could be due to kidney or urinary tract infection. Treatment may be needed if you experience symptoms such as painful and/or frequent urination. A repeat test on a midstream specimen of urine is advisable.',
            },
            {
                'test_code': 'RBC',
                'hl7_code': 'RBC^RBC',
                'lab_range': '=Neg',
                'negative_writeup': None,
                'positive_writeup': '**Presence of Red Blood Cells.**\nRed blood cells may occasionally be found in the urine of healthy individuals. Red blood cell counts of less than 5 cells/ul is usually of little significance. Your urinalysis indicated an increased amount of red cells in your urine. A repeat urine test on a first morning midstream specimen of urine after adequate hydration is advised for assessment. For females, as blood from menstruation can sometimes contaminate the urine sample, the repeat test should be done mid cycle to avoid contamination. Persistent haematuria may be due to kidney disease or renal tract pathology. If there is persistent blood present in the urine, further investigations may be required. If the further investigations are abnormal or if there is concurrent history of high blood pressure or abnormalities in the levels of urea and creatinine (kidney function test), a review with a specialist will be needed.',
            },
            {
                'test_code': 'Epithelials',
                'hl7_code': 'EPITH^EPITH',
                'lab_range': urine_epith_mapping,
                'negative_writeup': None,
                'positive_writeup': '**Presence of Epithelial Cells.**\nThese are cells lining the urinary tract. Increased epithelial cell counts in women may be a result of vaginal contamination. Occasionally, kidney or urinary tract malignancies can cause abnormal epithelial cells in the urine. Follow up urine assessment is recommended after adequate hydration.',
            },
            {
                'test_code': 'Crystals',
                'hl7_code': 'CRYSTAL AM^CRYSTAL AMT',
                'lab_range': urine_crystals_mapping,
                'negative_writeup': None,
                'positive_writeup': '**Presence of Crystals.**\nSmall amounts of crystals may be found in some individuals depending on the acidity of their urine. Excess crystals and for prolonged periods may precipitate stone formation. You are advised to repeat a midstream sampling after adequate hydration. Daily fluid intake should be about 2 litres.',
            },
            # # TODO: The earlier test code was wrong
            # {
            #     'test_code': 'Urine Microalbumin/Creatinine Ratio',
            #     'hl7_code': '', TODO: # xxxx^Microalbumin/Creatinine present but no values
            #     'positive_writeup': '**Your Urine Microalbumin / Creatinine Ratio is High.**\nThe urine microalbumin-to-creatinine ratio (UACR) is a commonly used to detect early kidney damage, particularly in people at risk for chronic kidney disease (CKD), such as those with diabetes, hypertension, or cardiovascular disease. Please consult the doctor for further advice.',
            # }
        ],
    },

    # Stool Analysis
    {
        'profile': Profiles.STOOL_ANALYSIS,
        'description': None,
        'tests': [
            {
                'test_code': 'Stool Occult Blood',
                'hl7_code': '2335-8^Occult Blood^QUE',
                'lab_range': '=Negative',
                'negative_writeup': None,
                'positive_writeup': '**Stool for occult blood was noted to be positive.**\nThis indicates that there was blood in your stool test. This could be due to dietary reasons such as poorly cooked meats or vitamin supplements. Other common reason would be piles (haemorrhoids). Three further repeat stool analysis for occult blood should be done. If persistently positive, a more detailed gastro-intestinal tract workout such as colonoscopy is needed to exclude more serious disease. Repeat tests should be done after abstinence from meat and iron or vitamin supplements for 5 days as these will cause interference with the stool test.',
            }
        ],
    },



    # # Mentioned to be removed as hormonal profile from health report as the ranges are  dependent on other factors, such as age, menstrual cycle, etc
    # {
    #     'profile': Profiles.HORMONE,
    #     'description': None,
    #     'tests': [
    #         {
    #             'test_code': 'Follicle Stimulating Hormone (FSH)',
    #             'hl7_code': '15067-2 ^FSH^',
    #             'lab_range': None,
    #             'low_writeup': "**Your FSH level is low.**\nFollicle Stimulating Hormone (FSH) is a key hormone produced by the pituitary gland that plays an important role in regulating the reproductive system. Low FSH levels can be associated with conditions such as hypopituitarism or hypothalamic dysfunction, which can affect overall reproductive function. Please consult the doctor for further instructions.",
    #             'high_writeup': "**Your FSH level is high.**\nFollicle Stimulating Hormone (FSH) is a key hormone produced by the pituitary gland that plays an important role in regulating the reproductive system. High FSH levels in woman especially in the early follicular phase—can indicate diminished ovarian reserve or the onset of menopause. High FSH in men may suggest primary testicular failure or decreased sperm production. Please consult the doctor for further instructions.",
    #         },
    #         {
    #             'test_code': 'Luteinising Hormone (LH)',
    #             'hl7_code': '10501-5 ^Luteinizing Hormone^',
    #             'lab_range': { 'M': "1.5-9.3", 'F': None} ,
    #             'low_writeup': "**Your LH level is low.**\nLuteinizing Hormone (LH) is a key reproductive hormone produced by the anterior pituitary gland. It plays an essential role in regulating reproductive functions in both men and women. Low LH levels may indicate pituitary or hypothalamic dysfunction, which can affect the overall reproductive hormone cascade in both sexes. Please consult the doctor for further instructions.",
    #             'high_writeup': "**Your LH level is high.**\nLuteinizing Hormone (LH) is a key reproductive hormone produced by the anterior pituitary gland. It plays an essential role in regulating reproductive functions in both men and women. High LH in men may indicate primary testicular failure. High LH in women may suggest PCOS or a decreased ovarian reserve, particularly in the context of infertility evaluations. Please consult the doctor for further instructions.",
    #         },
    #         {
    #             'test_code': 'Estradiol',
    #             'hl7_code': 'E2^Estradiol',
    #             'lab_range': None,
    #             'low_writeup': "**Your estradiol level is low.**\nEstradiol is the primary form of estrogen and plays a crucial role in reproductive and overall health. Low estradiol levels is often seen in menopausal women or may indicate diminished ovarian reserve. In men, low levels can sometimes affect bone density and overall hormonal balance. Please consult the doctor for further instructions.",
    #             'high_writeup': "**Your estradiol level is high.**\nEstradiol is the primary form of estrogen and plays a crucial role in reproductive and overall health. High estradiol level may suggest estrogen excess, which can occur with ovarian tumors, obesity, or hormone replacement therapy in women. In men, it might indicate issues like liver disease or exogenous estrogen exposure. Please consult the doctor for further instructions.",
    #         },
    #         {
    #             'test_code': 'Total Testosterone',
    #             'hl7_code': '14913-8 ^Testosterone^',
    #             'lab_range': { 'M': '6.85-23.23', 'F': '0.29-1.21' },
    #             'low_writeup': "**Your testosterone level is low.**\nLow testosterone levels in men can indicate conditions such as hypogonadism, which may lead to symptoms like reduced libido, fatigue, decreased muscle mass, and mood changes. Please consult the doctor for further instructions.",
    #             'high_writeup': "**Your testosterone level is high.**\nHigh testosterone levels in women may be associated with conditions such as polycystic ovary syndrome (PCOS) or adrenal gland disorders. Please consult the doctor for further instructions.",
    #         },
    #         {
    #             'test_code': 'Prolactin',
    #             'hl7_code': '15081-3 ^Prolactin^',
    #             'lab_range': None,
    #             'low_writeup': '**Your prolactin level is low.**\nProlactin is a hormone primarily produced by the pituitary gland. It plays a key role in breast milk production(lactation) but also influences metabolism, immune function, and reproductive health in both men and women. Low prolactin may be due to pituitary gland dysfunction. Please consult the doctor for further instructions.',
    #             'high_writeup': '**Your prolactin level is high.**\nProlactin is a hormone primarily produced by the pituitary gland. It plays a key role in breast milk production(lactation) but also influences metabolism, immune function, and reproductive health in both men and women. High prolactin may occur in normal situations like stress, sleep, intense exercise, pregnancy and breast feeding. Prolactin can also be raised in disease like prolactinoma (pituitary tumour), hypothyroidism, chronic kidney or liver disease or PCOS (polycystic ovary syndrome). Certain medications may cause the prolactin levels in the body to be raised. Please consult the doctor for further instructions',
    #         }
    #     ],
    # },

]