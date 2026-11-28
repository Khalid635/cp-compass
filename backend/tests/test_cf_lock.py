"""CF client cross-loop rate-limit test (batch 5 verification finding).

The CF client is a process-wide singleton, but _get runs on TWO event
loops at once: the main loop (dashboard / problemset / handle calls)
and a worker thread's own loop (asyncio.run in _run_job_sync). Its
rate-limit lock used to be an asyncio.Lock shared across those loops:
when the holder released from one loop, a waiter on the other loop was
never woken, wedging the sync worker forever on the second sync in a
process (job stuck 'running', lease expired, never reclaimed). The lock
is now a threading.Lock with slot reservation, which is loop-agnostic.
This test runs _get concurrently from two threads (two event loops)
and requires both to finish. No network: httpx is stubbed.
"""
import asyncio
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from app.cf import CFClient  # noqa: E402


class _FakeResp:
    def json(self):
        return {"status": "OK", "result": [{"id": 1}]}


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None):
        await asyncio.sleep(0.05)
        return _FakeResp()


def test_get_concurrent_across_loops(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    client = CFClient()
    # Force contention: pretend a call just happened, so the next caller
    # must wait inside the rate-limit section.
    client._last_call = time.monotonic()
    results = {}

    def run(tag):
        results[tag] = asyncio.run(client._get("/user.status", {"handle": "x"}))

    t1 = threading.Thread(target=run, args=("a",))
    t2 = threading.Thread(target=run, args=("b",))
    t1.start()
    time.sleep(0.1)
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)
    assert not t1.is_alive() and not t2.is_alive(), (
        "a _get call never returned (cross-loop lock wedge)"
    )
    assert results["a"] == [{"id": 1}]
    assert results["b"] == [{"id": 1}]
