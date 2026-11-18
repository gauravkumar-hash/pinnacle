import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.patient.webhook as wh
from utils.integrations.sgimed import ClientException

RATE_LIMITED = ClientException('SGiMed Error: /queue/1, 429, ')


def _no_wait(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(wh, 'asyncio', MagicMock(sleep=sleep))
    return sleep


def test_queue_event_waits_for_next_window_and_recovers(monkeypatch):
    sleep = _no_wait(monkeypatch)
    handler = AsyncMock(side_effect=[RATE_LIMITED, None])
    monkeypatch.setattr(wh, 'walkin_queue_number_update', handler)

    asyncio.run(wh.process_sgimed_event('visit.queue_number_changed', '1'))

    assert handler.await_count == 2
    assert 1 <= sleep.await_args.args[0] <= 61


def test_gives_up_after_3_attempts_without_raising(monkeypatch):
    _no_wait(monkeypatch)
    handler = AsyncMock(side_effect=RATE_LIMITED)
    monkeypatch.setattr(wh, 'walkin_queue_update', handler)

    asyncio.run(wh.process_sgimed_event('visit.queue_called', '1'))

    assert handler.await_count == 3


def test_invoice_fetch_is_retried_but_payment_posting_never_is(monkeypatch):
    _no_wait(monkeypatch)
    details = MagicMock()
    details.model_dump.return_value = {'invoice_id': 'i'}
    fetch = MagicMock(side_effect=[RATE_LIMITED, details])
    tele = MagicMock(side_effect=RATE_LIMITED)  # e.g. POST /invoice/payment got 429
    monkeypatch.setattr(wh, 'fetch_invoice_details', fetch)
    monkeypatch.setattr(wh, 'teleconsult_invoice_billed_webhook', tele)

    with pytest.raises(ClientException):
        asyncio.run(wh.process_sgimed_event('invoice.finalized', 'i'))

    assert fetch.call_count == 2
    tele.assert_called_once_with(invoice_id='i')


def test_endpoint_answers_200_even_when_the_work_fails(monkeypatch):
    process = AsyncMock(side_effect=RATE_LIMITED)
    monkeypatch.setattr(wh, 'process_sgimed_event', process)
    app = FastAPI()
    app.include_router(wh.router)
    app.dependency_overrides[wh.validate_sgimed_token] = lambda: {'data': {'event': 'visit.queue_called', 'object_reference': '1'}}

    resp = TestClient(app, raise_server_exceptions=False).post('/sgimed')

    assert resp.status_code == 200
    process.assert_awaited_once_with('visit.queue_called', '1')
