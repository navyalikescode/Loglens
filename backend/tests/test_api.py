import pytest
from httpx import ASGITransport, AsyncClient

import main as main_mod


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_analyse_with_text(client):
    r = await client.post(
        "/api/analyse",
        data={"log_text": "2024-01-15 12:00:00,000 ERROR m:1 hi\n"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "prompt_version" in body
    assert body.get("ok") is True


@pytest.mark.asyncio
async def test_analyse_with_file(client):
    files = {"log_file": ("t.log", b"2024-01-15 12:00:00,000 ERROR m:1 hi\n", "text/plain")}
    r = await client.post("/api/analyse", files=files)
    assert r.status_code == 200
    assert r.json().get("ok") is True


@pytest.mark.asyncio
async def test_analyse_no_input(client):
    r = await client.post("/api/analyse", data={})
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d.get("prompt_version")


@pytest.mark.asyncio
async def test_analyse_file_too_large(client, monkeypatch):
    monkeypatch.setattr(main_mod, "MAX_LOG_SIZE_MB", 0)
    files = {"log_file": ("big.log", b"x" * 2048, "text/plain")}
    r = await client.post("/api/analyse", files=files)
    assert r.status_code == 413
    assert r.json()["detail"]["prompt_version"]


@pytest.mark.asyncio
async def test_504_has_prompt_version():
    import asyncio

    from asgi_lifespan import LifespanManager

    from main import app

    async def slow_process(*_args, **_kwargs):
        await asyncio.sleep(60)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(main_mod.LogProcessor, "aprocess", slow_process)
        m.setattr(main_mod, "ASK_TIMEOUT_SECONDS", 1)
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as c:
                r = await c.post("/api/analyse", data={"log_text": "a\n"}, timeout=15.0)
    assert r.status_code == 504
    assert r.json()["prompt_version"]


@pytest.mark.asyncio
async def test_request_id_header(client):
    r = await client.get("/api/health")
    assert "x-request-id" in {k.lower() for k in r.headers.keys()}


@pytest.mark.asyncio
async def test_rate_limit(client):
    codes = []
    for _ in range(15):
        r = await client.post("/api/analyse", data={"log_text": "INFO ok\n"})
        codes.append(r.status_code)
        if r.status_code == 429:
            break
    assert 429 in codes
