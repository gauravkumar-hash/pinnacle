from datetime import datetime
import os
import requests
import time

import pytz
sgtz = pytz.timezone("Asia/Singapore") 

print(f"{datetime.now(sgtz)}: Sleeping for 10 secs.")
time.sleep(10)

BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')
CRON_API_KEY = os.getenv('CRON_API_KEY', '')

url = f"{BACKEND_API_URL}/api/crons/teleconsults/reset"
headers = {
    "Authorization": f"Bearer {CRON_API_KEY}"
}
response = requests.get(url, headers=headers)

print(url)
print(response.status_code)
print("\n".join(response.json()))
