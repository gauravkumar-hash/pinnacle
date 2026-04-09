import httpx
from config import BUNJS_SERVER_URL, SUPABASE_WEBHOOK_API_KEY

def get_health_report_pdf(payload: dict):
    # BUNJS_SERVER_URL = 'http://localhost:4001'
    response = httpx.post(
        f'{BUNJS_SERVER_URL}/api/health-report-pdf',
        headers={
          'Content-Type': 'application/json',
          'Authorization': f'Bearer {SUPABASE_WEBHOOK_API_KEY}'
        },
        json=payload,
        timeout=15,
    )
    return response.content
