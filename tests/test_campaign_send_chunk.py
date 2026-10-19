from types import SimpleNamespace

from scheduler_actions import campaign_updates as cu


class FakeResponse:
    id = "ticket"

    def validate_response(self):
        pass


def test_malformed_token_does_not_fail_the_rest_of_the_chunk(monkeypatch):
    '''
    Given: A chunk where one recipient has a malformed push token
    When: The chunk is sent
    Then: Only that row is marked invalid_token; the valid rows are sent
    '''
    sent = []
    monkeypatch.setattr(cu, "_publish", lambda client, msgs: sent.extend(msgs) or [FakeResponse() for _ in msgs])
    campaign = SimpleNamespace(id="c", type="consent_notice", title="t", body="b", data=None, sent_count=0, failed_count=0)
    good = [SimpleNamespace(account_id=i, push_token=f"ExponentPushToken[{i}]", status="pending", attempts=0) for i in range(3)]
    bad = SimpleNamespace(account_id=99, push_token="fcm-token-abc", status="pending", attempts=0)
    db = SimpleNamespace(add_all=lambda rows: None)

    cu._send_chunk(db, campaign, None, [good[0], bad, good[1], good[2]])

    assert [m.to for m in sent] == [r.push_token for r in good]
    assert all(m.data["campaign_id"] == "c" for m in sent)  # lets the app report taps
    assert all(r.status == "sent" for r in good)
    assert bad.status == "invalid_token"
    assert campaign.sent_count == 3 and campaign.failed_count == 1


def test_receipts_without_answer_do_not_block_later_rows(monkeypatch):
    '''
    Given: A full batch of tickets Expo has no receipt for, followed by newer tickets
    When: The receipt poller runs one tick
    Then: It moves past the unanswered batch and records the newer receipts
    '''
    monkeypatch.setattr(cu, "RECEIPT_POLL_BATCH", 2)
    campaign = SimpleNamespace(delivered_count=0, undelivered_count=0)
    rows = [
        SimpleNamespace(id=i, campaign_id="c", expo_ticket_id=f"t{i}", receipt_status=None, receipt_checked_at=None)
        for i in range(1, 5)
    ]
    monkeypatch.setattr(
        cu, "_receipt_rows",
        lambda db, after_id, cutoff: [r for r in rows if r.id > after_id and r.receipt_status is None][:2],
    )

    class FakeResp:
        def __init__(self, ids):
            # t1/t2 never get an answer (expired or unknown); t3/t4 are delivered
            self.data = {i: {"status": "ok"} for i in ids if i in ("t3", "t4")}

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": self.data}

    monkeypatch.setattr(cu.requests.Session, "post", lambda self, url, json, timeout: FakeResp(json["ids"]))
    db = SimpleNamespace(get=lambda model, id: campaign, commit=lambda: None)

    cu.check_campaign_receipts(db)

    assert [r.receipt_status for r in rows] == [None, None, "ok", "ok"]
    assert campaign.delivered_count == 2
