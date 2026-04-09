import os
from dotenv import load_dotenv
from firebase_admin import credentials
import firebase_admin
from supabase import create_client
import redis
import stripe
from pathlib import Path
import logging
# Load environment variables from .env file

def load_environment():
    """
    Load environment variables based on ENV setting
    Priority:
    1. .env.{environment} file
    2. .env file (fallback)
    """
    # Get environment from ENV variable, default to 'development'
    env_name = os.getenv('ENV', 'development').lower()
    
    # Matches four paths for .env files:
    # ../.env.{ENV}
    # ./.env.{ENV}
    # ../.env
    # ./.env
    specific_env_path = Path(f'.env.{env_name}')
    default_env_path = Path('.env')
    parent_path = Path(__file__).parent
    dotenv_path = None
    if (parent_path / specific_env_path).exists():
        dotenv_path = parent_path / specific_env_path
    elif specific_env_path.exists():
        dotenv_path = specific_env_path
    elif (parent_path / default_env_path).exists():
        dotenv_path = parent_path / default_env_path
    elif default_env_path.exists():
        dotenv_path = default_env_path
        
    if dotenv_path:
        load_dotenv(dotenv_path)
        print(f"Loaded environment from {dotenv_path}")

load_environment()

# Custom environment variables
BACKEND_ENVIRONMENT = os.getenv("BACKEND_ENVIRONMENT", '')
BACKEND_API_URL = os.getenv("BACKEND_API_URL", '')
MOCK_SMS = os.getenv("MOCK_SMS", "False") == "True"
CURRENT_APP_VERSION = int(os.getenv("CURRENT_APP_VERSION", 1))
MIN_SUPPORTED_APP_VERSION = int(os.getenv("MIN_SUPPORTED_APP_VERSION", 1))
EXPO_PUBLIC_API_KEY = os.getenv("EXPO_PUBLIC_API_KEY", '')
EXPO_PATIENT_TOKEN = os.getenv("EXPO_PATIENT_TOKEN", '')
EXPO_DOCTOR_TOKEN = os.getenv("EXPO_DOCTOR_TOKEN", '')
CRON_API_KEY = os.getenv("CRON_API_KEY", '')
ADMIN_WEB_URL = os.getenv("ADMIN_WEB_URL", '')
WALK_IN_START_TIME_DELAY = int(os.getenv("WALK_IN_START_TIME_DELAY", 15))

# SGiMed API credentials
SGIMED_API_URL = os.getenv('SGIMED_API_URL')
SGIMED_API_KEY = os.getenv('SGIMED_API_KEY')
SGIMED_DEFAULT_BRANCH_ID = os.getenv('SGIMED_DEFAULT_BRANCH_ID') # Branch used for registering new users
SGIMED_TELEMED_APPT_TYPE_ID = os.getenv('SGIMED_TELEMED_APPT_TYPE_ID', '')
SGIMED_SA_PCP_BRANCH_ID = os.getenv('SGIMED_SA_PCP_BRANCH_ID', '')
SGIMED_MEDICATION_ITEM_TYPE = os.getenv('SGIMED_MEDICATION_ITEM_TYPE') # This is used to determine if an invoice has medication to be dispensed
SGIMED_GST_RATE = float(os.getenv('SGIMED_GST_RATE', 0.09))
# SGIMED_PAYMENT_NETS_CLICK_ID = os.getenv('SGIMED_PAYMENT_NETS_CLICK_ID')
# SGIMED_PAYMENT_PAYNOW_ID = os.getenv('SGIMED_PAYMENT_PAYNOW_ID')
# SGIMED_SA_PCP_RATE_ID = os.getenv('SGIMED_SA_PCP_RATE_ID')
# May not need this since once payment is made, it should directly be reflected on the invoice
# SGIMED_PAYMENT_SGIMED_PAY_ID = '@SGiMED.Pay' 
SGIMED_WEBHOOK_PUBLIC_KEY = os.getenv("SGIMED_WEBHOOK_PUBLIC_KEY", '').replace('\\n', '\n')
# Postgres Credentials
POSTGRES_URL = os.getenv("POSTGRES_URL", '')
POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", 40))

# Firebase credentials
raw_creds = {
    "type": os.getenv('FIREBASE_TYPE'),
    "project_id": os.getenv('FIREBASE_PROJECT_ID'),
    "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.getenv('FIREBASE_PRIVATE_KEY', "").replace('\\n', '\n'),
    "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.getenv('FIREBASE_CLIENT_ID'),
    "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
    "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
    "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
    "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL'),
    "universe_domain": os.getenv('FIREBASE_UNIVERSE_DOMAIN')
}
try:
    firebase_creds = credentials.Certificate(raw_creds)
    firebase_app = firebase_admin.initialize_app(firebase_creds)
except Exception as e:
    firebase_app = None
    print(f"⚠️ Firebase initialization failed: {e}. Firebase features will be unavailable.")

# SMSDome credentials
SMSDOME_URL = os.getenv("SMSDOME_URL", "")
SMSDOME_APPID = os.getenv("SMSDOME_APPID", "")
SMSDOME_APPSECRET = os.getenv("SMSDOME_APPSECRET", "")

# Email configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
MOCK_EMAIL = os.getenv("MOCK_EMAIL", "False") == "True"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")

try:
    logger.info("Connecting to Redis...")
    
    if REDIS_URL:
        # Masking the URL for safe logging
        masked_url = REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL
        logger.info(f"Using REDIS_URL: redis://****@{masked_url}")
        redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    else:
        host = os.getenv("REDIS_HOST", "localhost")
        port = os.getenv("REDIS_PORT", 6379)
        logger.info(f"Using manual config - Host: {host}, Port: {port}")
        redis_client = redis.StrictRedis(
            host=host,
            port=int(port),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True,
            socket_timeout=5
        )

    # Performance & Connection check
    import time
    start_time = time.time()
    redis_client.ping()
    latency = (time.time() - start_time) * 1000
    
    logger.info(f"✅ Redis connection established! Latency: {latency:.2f}ms")

except Exception as e:
    logger.error("❌ CRITICAL: Redis connection failed.")
    logger.error(f"Error Type: {type(e).__name__}")
    logger.error(f"Error Message: {str(e)}")
    # We set it to None so the app starts, but logic must handle this
    redis_client = None
# Logging
SENTRY_DSN = os.getenv('SENTRY_DSN', '')

# Stripe Credentials
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Zoom Credentials
ZOOM_APP_KEY = os.getenv('ZOOM_APP_KEY', '')
ZOOM_APP_SECRET = os.getenv('ZOOM_APP_SECRET', '')

# Supabase Credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
SUPABASE_WEBHOOK_API_KEY = os.getenv('SUPABASE_WEBHOOK_API_KEY', '')
SUPABASE_UPLOAD_BUCKET = os.getenv('SUPABASE_UPLOAD_BUCKET', '')
SUPABASE_PRIVATE_BUCKET = os.getenv('SUPABASE_PRIVATE_BUCKET', '')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUNJS_SERVER_URL = os.getenv('BUNJS_SERVER_URL', '')

# APNS Credentials
APNS_AUTH_KEY = os.getenv('APNS_AUTH_KEY', '').replace('\\n', '\n')
APNS_KEY_ID = os.getenv('APNS_KEY_ID', '')
APNS_TEAM_ID = os.getenv('APNS_TEAM_ID', '')
APNS_TOPIC = os.getenv('APNS_TOPIC', 'sg.com.pinnaclefamilyclinic.test.pinnaclesgplus.voip')
APNS_USE_SANDBOX = os.getenv('APNS_USE_SANDBOX', 'True') == 'True'

# 2C2P Credentials
PAYMENT_2C2P_ENDPOINT = os.getenv('PAYMENT_2C2P_ENDPOINT', '')
PAYMENT_2C2P_MERCHANT_SHA_KEY = os.getenv('PAYMENT_2C2P_MERCHANT_SHA_KEY', '')
PAYMENT_2C2P_MERCHANT_ID = os.getenv('PAYMENT_2C2P_MERCHANT_ID', '')
PAYMENT_2C2P_CURRENCY_CODE = os.getenv('PAYMENT_2C2P_CURRENCY_CODE', '')
if BACKEND_ENVIRONMENT == 'production' and (
    not PAYMENT_2C2P_ENDPOINT or not PAYMENT_2C2P_MERCHANT_SHA_KEY
    or not PAYMENT_2C2P_MERCHANT_ID or not PAYMENT_2C2P_CURRENCY_CODE
):
    raise ValueError("2C2P credentials are not set")
elif not PAYMENT_2C2P_ENDPOINT or not PAYMENT_2C2P_MERCHANT_SHA_KEY or not PAYMENT_2C2P_MERCHANT_ID or not PAYMENT_2C2P_CURRENCY_CODE:
    print("⚠️ 2C2P credentials are not set. 2C2P payment features will be unavailable.")

# ⚠️ PAYMENT AUTHORIZATION FEATURE FLAGS - PRODUCTION SAFETY
# CRITICAL: Keep these OFF initially when deploying to production
# See documentation/CRITICAL_PRODUCTION_WARNING.md for safe rollout plan
ENABLE_PAYMENT_AUTHORIZATION = os.getenv('ENABLE_PAYMENT_AUTHORIZATION', 'False') == 'True'
# Rollout percentage (0-100): What % of eligible users should get auth/capture flow
# Start with 0, then gradually increase: 1 -> 10 -> 50 -> 100
AUTHORIZATION_ROLLOUT_PERCENTAGE = int(os.getenv('AUTHORIZATION_ROLLOUT_PERCENTAGE', 0))
# Test user IDs that should always get authorization flow (regardless of rollout %)
# Format: comma-separated list of patient IDs
AUTHORIZATION_TEST_USER_IDS = os.getenv('AUTHORIZATION_TEST_USER_IDS', '').split(',') if os.getenv('AUTHORIZATION_TEST_USER_IDS') else []
# Patient types that are eligible for authorization flow (others get immediate charge)
# Default: only private patients (migrant workers always use PayNow = immediate charge)
AUTHORIZATION_ENABLED_PATIENT_TYPES = os.getenv('AUTHORIZATION_ENABLED_PATIENT_TYPES', 'private_patient').split(',') if os.getenv('AUTHORIZATION_ENABLED_PATIENT_TYPES') else []
# Authorization expiry time in minutes (2C2P typically allows 7-30 days, we default to 24 hours)
AUTHORIZATION_EXPIRY_MINUTES = int(os.getenv('AUTHORIZATION_EXPIRY_MINUTES', 1440))  # 24 hours
# Auto-capture after consultation (True) or require manual capture (False)
AUTO_CAPTURE_AFTER_CONSULTATION = os.getenv('AUTO_CAPTURE_AFTER_CONSULTATION', 'True') == 'True'
# Fallback to immediate charge on authorization failure (recommended: True for safety)
FALLBACK_TO_IMMEDIATE_CHARGE_ON_AUTH_FAILURE = os.getenv('FALLBACK_TO_IMMEDIATE_CHARGE_ON_AUTH_FAILURE', 'True') == 'True'

# Yuu Credentials
YUU_CLIENT_ID = os.getenv('YUU_CLIENT_ID', '')
YUU_CLIENT_SECRET = os.getenv('YUU_CLIENT_SECRET', '')
YUU_API_URL = os.getenv('YUU_API_URL', '')
YUU_REDIRECT_URI = os.getenv('YUU_REDIRECT_URI', '')
YUU_PUBLIC_KEY = os.getenv('YUU_PUBLIC_KEY', '')
YUU_PINNACLE_PRIVATE_KEY = os.getenv('YUU_PINNACLE_PRIVATE_KEY', '')
YUU_PINNACLE_PRIVATE_KEYPHRASE = os.getenv('YUU_PINNACLE_PRIVATE_KEYPHRASE', '')
YUU_SGIMED_COMPANY_ID = os.getenv('YUU_SGIMED_COMPANY_ID', '17506409518296369')
# Yuu Integration Configuration
YUU_AWS_ACCESS_KEY = os.getenv("YUU_AWS_ACCESS_KEY", "")
YUU_AWS_SECRET_ACCESS_KEY = os.getenv("YUU_AWS_SECRET_ACCESS_KEY", "")
YUU_IAM_ROLE = os.getenv("YUU_IAM_ROLE", "")
YUU_S3_BUCKET = os.getenv("YUU_S3_BUCKET", "")
YUU_S3_PATH = os.getenv("YUU_S3_PATH", "")
YUU_BRAND_CODE = os.getenv("YUU_BRAND_CODE", "")
