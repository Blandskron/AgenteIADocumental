from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.shared.constants import MAX_UPLOAD_BODY_BYTES


class UploadBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != "/api/v1/documents/upload"
        ):
            await self._app(scope, receive, send)
            return

        detail = "Upload request exceeds the allowed size."
        length = Headers(scope=scope).get("content-length", "")
        length = length.lstrip("0")
        if length.isascii() and length.isdecimal() and (
            len(length) > len(str(MAX_UPLOAD_BODY_BYTES)) or int(length) > MAX_UPLOAD_BODY_BYTES
        ):
            await JSONResponse({"detail": detail}, status_code=413)(scope, receive, send)
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_UPLOAD_BODY_BYTES:
                    raise HTTPException(status_code=413, detail=detail)
            return message

        await self._app(scope, limited_receive, send)
