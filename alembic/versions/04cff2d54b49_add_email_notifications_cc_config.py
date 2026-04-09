"""Add EMAIL_NOTIFICATIONS_CC config

Revision ID: 04cff2d54b49
Revises: 0956d4e3002a
Create Date: 2025-10-13 02:42:00.000000

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04cff2d54b49'
down_revision: Union[str, None] = '72aee85898c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Define the email notifications configuration
    config_value = {
        "from_email": "noreply@pinnaclefamilyclinic.com.sg",
        "cc_emails": ["connect@pinnaclefamilyclinic.com.sg"],
        "appointments_template": {
            "title": "New Appointment Booking - PinnacleSG+ App",
            "body": """Dear Team,

Please note that a new appointment has been made via the PinnacleSG+ App.

Clinic Selection: {clinic_name}
Patient: {patient_name}
Date and Time: {appointment_date}, {appointment_time}
Service Selection: {service_names}
Corporate Code: {corporate}
Pre-Payment: {prepayment}

Kindly contact the patient to confirm the appointment.

Thank you.

Best regards,
Pinnacle Family Clinic"""
        }
    }

    # Add EMAIL_NOTIFICATIONS_CC config to backend_configs
    # Use parameterized query to prevent SQL injection
    from sqlalchemy import text

    conn = op.get_bind()
    conn.execute(
        text("""
            INSERT INTO backend_configs (key, value, value_type, description, category, created_at, updated_at)
            VALUES (
                :key,
                :value,
                :value_type,
                :description,
                :category,
                NOW(),
                NOW()
            )
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                value_type = EXCLUDED.value_type,
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                updated_at = NOW()
        """),
        {
            "key": "EMAIL_NOTIFICATIONS_CC",
            "value": json.dumps(config_value),
            "value_type": "json",
            "description": "Email notification configuration: from_email, cc_emails (list), and appointments_template (title and body with template variables)",
            "category": "email"
        }
    )


def downgrade() -> None:
    # Remove EMAIL_NOTIFICATIONS_CC config
    from sqlalchemy import text
    conn = op.get_bind()
    conn.execute(
        text("DELETE FROM backend_configs WHERE key = :key"),
        {"key": "EMAIL_NOTIFICATIONS_CC"}
    )
