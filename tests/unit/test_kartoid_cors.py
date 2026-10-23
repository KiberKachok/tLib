# Unit tests for middlewares/kartoid_cors.py
# Описание: Проверяет, что Access-Control-Allow-Origin получает только KARTOID_ORIGIN и только
#           на GET/HEAD /api/archive/*/file/*, в том числе ответ 429 от RateLimitMiddleware.

from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from config import KARTOID_ORIGIN
from middlewares.kartoid_cors import KartoidCORSMiddleware
from middlewares.rate_limit import RateLimitMiddleware

# Адрес трека для фрейма: путь в ZIP закодирован одним сегментом
TRACK_URL = "/api/archive/01943-TLIB/file/%D1%82%D1%80%D0%B5%D0%BA%D0%B8%2Fday1.gpx?original=1"


async def _ok(scope, receive, send):
    await PlainTextResponse("ok")(scope, receive, send)


def _client(requests_per_minute: int | None = None) -> TestClient:
    """Middleware в порядке app.py: CORS снаружи лимита."""
    return TestClient(KartoidCORSMiddleware(RateLimitMiddleware(_ok, requests_per_minute=requests_per_minute)))


class TestKartoidCORS:
    def test_kartoid_origin_gets_header(self):
        client = _client()
        for resp in (client.get(TRACK_URL, headers={"Origin": KARTOID_ORIGIN}),
                     client.head(TRACK_URL, headers={"Origin": KARTOID_ORIGIN})):
            assert resp.status_code == 200
            assert resp.headers["access-control-allow-origin"] == KARTOID_ORIGIN
            assert resp.headers["vary"] == "Origin"

    def test_other_origin_gets_no_header(self):
        resp = _client().get(TRACK_URL, headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in resp.headers
        # Без Vary кеш браузера отдал бы фрейму ответ без заголовка
        assert resp.headers["vary"] == "Origin"

    def test_other_paths_and_methods_stay_closed(self):
        client = _client()
        for path in ("/api/archive/01943-TLIB/contents", "/api/archive/01943-TLIB/all-tracks"):
            resp = client.get(path, headers={"Origin": KARTOID_ORIGIN})
            assert "access-control-allow-origin" not in resp.headers, path
        resp = client.post(TRACK_URL, headers={"Origin": KARTOID_ORIGIN})
        assert "access-control-allow-origin" not in resp.headers

    def test_rate_limit_429_gets_header(self):
        client = _client(requests_per_minute=1)
        responses = [client.get(TRACK_URL, headers={"Origin": KARTOID_ORIGIN}) for _ in range(2)]
        assert [resp.status_code for resp in responses] == [200, 429]
        assert responses[1].headers["access-control-allow-origin"] == KARTOID_ORIGIN
