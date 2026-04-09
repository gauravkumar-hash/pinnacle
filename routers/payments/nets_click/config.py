from dotenv import load_dotenv
import os

load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT", "")
NETS_CLICK_DOMAIN_NAME = os.getenv("NETS_CLICK_DOMAIN_NAME", "")
NETS_CLICK_API_STATUS_DOMAIN_NAME = os.getenv("NETS_CLICK_API_STATUS_DOMAIN_NAME", "")
NETS_CLICK_API_KEY = os.getenv("NETS_CLICK_API_KEY", "")
NETS_CLICK_SECRET = os.getenv("NETS_CLICK_SECRET", "")

if not (NETS_CLICK_DOMAIN_NAME and NETS_CLICK_API_STATUS_DOMAIN_NAME and ENVIRONMENT):
    raise Exception("DOMAIN_NAME and API_STATUS_DOMAIN_NAME must be set in .env file")

NETS_CLICK_TID = os.getenv("NETS_CLICK_TID", "")
NETS_CLICK_RID = os.getenv("NETS_CLICK_RID", "")
if not (NETS_CLICK_TID and NETS_CLICK_RID):
    raise Exception("TID and RID must be set in .env file")
