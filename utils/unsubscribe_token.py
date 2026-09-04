"""
Stateless opt-out token for the *web* unsubscribe link (used only when the consent notice is
also sent by SMS / email to patients with no push token). Push-only deployments don't need this.

Format:  <account_id>.<hex hmac-sha256(account_id, secret)>
The token only ever grants opt-*out*, so a leaked link cannot re-subscribe anyone.

Secret: env var UNSUBSCRIBE_TOKEN_SECRET. Set it in staging / production.
"""

import hashlib
import hmac
import os

_SECRET = os.getenv("UNSUBSCRIBE_TOKEN_SECRET", "change-me-in-env").encode()


def make_unsubscribe_token(account_id: str) -> str:
    account_id = str(account_id)
    sig = hmac.new(_SECRET, account_id.encode(), hashlib.sha256).hexdigest()
    return f"{account_id}.{sig}"


def verify_unsubscribe_token(token: str) -> str | None:
    """Return the account_id if the token is valid, else None."""
    try:
        account_id, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(_SECRET, account_id.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected):
        return account_id
    return None
