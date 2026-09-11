"""add marketing / consent notification tables

Revision ID: e5f6a7b8c9d0
Revises: c0d1e2f3a4b5
Create Date: 2026-09-04

Creates:
  - patient_notification_preferences
  - backend_notification_campaigns
  - backend_notification_campaign_recipients

No native ENUM types: the small enumerations are stored as plain VARCHAR and validated in
application code, so this migration applies cleanly on local / staging / production.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_notification_preferences",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "marketing_opt_in", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("consent_notice_sent_at", sa.DateTime(), nullable=True),
        sa.Column("opted_out_at", sa.DateTime(), nullable=True),
        sa.Column("opt_out_source", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["account_id"], ["patient_accounts.id"]),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.create_table(
        "backend_notification_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column(
            "status", sa.String(), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column(
            "total_recipients", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "sent_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "backend_notification_campaign_recipients",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("push_token", sa.String(), nullable=False),
        sa.Column(
            "status", sa.String(), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["backend_notification_campaigns.id"]
        ),
        sa.ForeignKeyConstraint(["account_id"], ["patient_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backend_notification_campaign_recipients_campaign_id",
        "backend_notification_campaign_recipients",
        ["campaign_id"],
    )
    op.create_index(
        "ix_backend_notification_campaign_recipients_account_id",
        "backend_notification_campaign_recipients",
        ["account_id"],
    )
    op.create_index(
        "ix_campaign_recipient_campaign_status",
        "backend_notification_campaign_recipients",
        ["campaign_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_recipient_campaign_status",
        table_name="backend_notification_campaign_recipients",
    )
    op.drop_index(
        "ix_backend_notification_campaign_recipients_account_id",
        table_name="backend_notification_campaign_recipients",
    )
    op.drop_index(
        "ix_backend_notification_campaign_recipients_campaign_id",
        table_name="backend_notification_campaign_recipients",
    )
    op.drop_table("backend_notification_campaign_recipients")
    op.drop_table("backend_notification_campaigns")
    op.drop_table("patient_notification_preferences")
