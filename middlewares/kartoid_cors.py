# Kartoid CORS Middleware для TlibWebApp
# Описание: Добавляет Access-Control-Allow-Origin: KARTOID_ORIGIN к ответам GET/HEAD /api/archive/*/file/*:
#           фрейм Kartoid на вкладке «Карта» сам скачивает треки отчёта из браузера.

import re

from starlette.datastructures import Headers, MutableHeaders

from config import KARTOID_ORIGIN

_ARCHIVE_FILE_RE = re.compile(r"^/api/archive/[^/]+/file/")


class KartoidCORSMiddleware:
    """
    ASGI middleware: Access-Control-Allow-Origin для KARTOID_ORIGIN на файлах архивов.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] not in ("GET", "HEAD")
                or not _ARCHIVE_FILE_RE.match(scope["path"])):
            await self.app(scope, receive, send)
            return

        allowed = Headers(scope=scope).get("origin") == KARTOID_ORIGIN

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.add_vary_header("Origin")
                if allowed:
                    headers["Access-Control-Allow-Origin"] = KARTOID_ORIGIN
            await send(message)

        await self.app(scope, receive, send_wrapper)
