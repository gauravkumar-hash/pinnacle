# Medical App Backend

> Synced from [pinnaclesg-monorepo](https://github.com/GRMedicalApp/pinnaclesg-monorepo) - 2025-12-30

- Hosted on [Render](https://docs.render.com/deploy-fastapi)
- uvicorn main:app --host 0.0.0.0 --port $PORT

# Development Environment
- Get `.env` file from admin
- Start environment `python3 -m venv .venv` Python 3.13
- Activate environment `source .venv/bin/activate`
- Install dependencies `pip install -r requirements.txt`

```
uv run ruff check
```

- Replace the domain with domain provided from ngrok
```
ngrok http --domain=amazed-mink-trivially.ngrok-free.app 8000
```

# Supabase Configuration
https://supabase.com/dashboard/project/ksminnjzhpczzmtoztgt/settings/auth
- SMTP Provider Settings
https://supabase.com/dashboard/project/ksminnjzhpczzmtoztgt/auth/rate-limits
- Rate limit for sending emails
https://supabase.com/dashboard/project/ksminnjzhpczzmtoztgt/auth/url-configuration
- Site URL
https://supabase.com/dashboard/project/ksminnjzhpczzmtoztgt/settings/database
- Pool Size

Update Direct Connections [Source](https://supabase.com/docs/guides/troubleshooting/how-to-change-max-database-connections-_BQ8P5#configuring-direct-connections-limits)
```
npx supabase --experimental --project-ref yaadelemrtuxfyxayxpu postgres-config update --config max_connections=600
```

# Update Webhooks
- Stripe: https://dashboard.stripe.com/test/webhooks/we_1PNrE8Cu0dFCVV90GNIOkmwh
    - https://pinnacle-api.geddit-apps.com/api/webhook/stripe
- SGiMed: https://clinic.hb-uat.sgimed.com/system-general-settings/api
    - https://pinnacle-api.geddit-apps.com/api/webhook/sgimed
- Supabase: https://supabase.com/dashboard/project/ksminnjzhpczzmtoztgt/database/hooks
    - https://pinnacle-api.geddit-apps.com/api/webhook/supabase/teleconsults
    - Authorization: Bearer <SUPABASE_WEBHOOK_API_KEY>
    - Timeout: 5000


# FastAPI Examples
```python
req_examples = Body(
    openapi_examples={
        "normal": {
            "summary": "A normal example",
            "description": "A **normal** item works correctly.",
            "value": {
                "mode": "nets",
                "branch_id": "<branch_id>",
            }
        },
        "invalid": {
            "summary": "Invalid data is rejected with an error",
            "description": "A **normal** item works correctly.",
            "value": {
                "mode": "nets1",
                "branch_id": "<branch_id>",
            }
        }
    }
)

class BranchesResp(BaseModel):
    branches: list[Branch]  = Field(default=[], examples=[[Branch(id="branch_1", name="Branch 1", address="Address 1")]])
```

# Branch Module
Tables (pinnacle_services, pinnacle_branches)

# Appointment Module
1. Add the following to `backend_configs` table in Postgres
```json
{
    "key": "APPOINTMENT_CONSTANTS",
    "value": {
        "DEFAULT_ONSITE_BRANCH_ID": "CPV",
        "DEFAULT_DOCTOR_ID": "17237048450000297"
    }
}
```

2. Configure SGiMed appointment type IDs directly on branches
   - Each branch in the `pinnacle_branches` table should have a `sgimed_appointment_type_id` field
   - This field is used when creating appointments in SGiMed for that specific branch
   - For onsite branches, they inherit the routing from their associated main branch via `sgimed_branch_id`
   - Example: Update branch with `sgimed_appointment_type_id`:
   ```sql
   UPDATE pinnacle_branches
   SET sgimed_appointment_type_id = '17470297099939193'
   WHERE sgimed_branch_id = 'CPV';
   ```
