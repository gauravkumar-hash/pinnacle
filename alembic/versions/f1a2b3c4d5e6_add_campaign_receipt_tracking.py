"""add push-receipt / delivery tracking to notification campaigns

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-09-06

Adds:
  - backend_notification_campaign_recipients.expo_ticket_id     (Expo push ticket id)
  - backend_notification_campaign_recipients.receipt_status      (ok | error, from Expo getReceipts)
  - backend_notification_campaign_recipients.receipt_error       (Expo error detail, if any)
  - backend_notification_campaign_recipients.receipt_checked_at  (when the receipt was polled)
  - backend_notification_campaigns.delivered_count               (receipts confirmed delivered)
  - backend_notification_campaigns.undelivered_count             (receipts came back with an error)

"Sent" means Expo accepted the push. "Delivered" means Expo's receipt later confirmed the
push reached FCM / APNs. Opens are NOT tracked here - that needs an app-side event.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "backend_notification_campaign_recipients",
        sa.Column("expo_ticket_id", sa.String(), nullable=True),
    )
    op.add_column(
        "backend_notification_campaign_recipients",
        sa.Column("receipt_status", sa.String(), nullable=True),
    )
    op.add_column(
        "backend_notification_campaign_recipients",
        sa.Column("receipt_error", sa.String(), nullable=True),
    )
    op.add_column(
        "backend_notification_campaign_recipients",
        sa.Column("receipt_checked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "backend_notification_campaigns",
        sa.Column(
            "delivered_count", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "backend_notification_campaigns",
        sa.Column(
            "undelivered_count", sa.Integer(), server_default="0", nullable=False
        ),
    )
    # Hot path for the receipt-poller: "sent rows for this campaign with no receipt yet".
    op.create_index(
        "ix_campaign_recipient_receipt_poll",
        "backend_notification_campaign_recipients",
        ["campaign_id", "status", "receipt_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_recipient_receipt_poll",
        table_name="backend_notification_campaign_recipients",
    )
    op.drop_column("backend_notification_campaigns", "undelivered_count")
    op.drop_column("backend_notification_campaigns", "delivered_count")
    op.drop_column("backend_notification_campaign_recipients", "receipt_checked_at")
    op.drop_column("backend_notification_campaign_recipients", "receipt_error")
    op.drop_column("backend_notification_campaign_recipients", "receipt_status")
    op.drop_column("backend_notification_campaign_recipients", "expo_ticket_id")
