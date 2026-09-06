#!/usr/bin/env python3
"""
One-shot marketing/notification campaign worker - for manual testing without the scheduler.

Does exactly what the two scheduler jobs do, once each, then exits:
  1. process_sending_campaigns(db)  - push one batch for every campaign in 'sending'
  2. check_campaign_receipts(db)    - poll Expo delivery receipts for already-sent rows

Run it repeatedly until the campaign flips to 'completed'.

Usage:
    uv run cli/campaign_worker_once.py
    # or, in an env where deps are already installed:
    python -m cli.campaign_worker_once
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from models import SessionLocal  # noqa: E402
from scheduler_actions.campaign_updates import (  # noqa: E402
    check_campaign_receipts,
    process_sending_campaigns,
)


def main() -> None:
    with SessionLocal() as db:
        print("--- process_sending_campaigns ---")
        process_sending_campaigns(db)
        print("--- check_campaign_receipts ---")
        check_campaign_receipts(db)
    print("done")


if __name__ == "__main__":
    main()
