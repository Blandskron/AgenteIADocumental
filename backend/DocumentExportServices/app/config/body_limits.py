import asyncio
from threading import BoundedSemaphore

from starlette.responses import JSONResponse

from app.config.export_limits import MAX_BODY


class ExportBodyLimits:
    def __init__(self, app):
        self.app = app
        self.slots = BoundedSemaphore(2)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        async def fail(status, detail):
            await JSONResponse({"detail": detail}, status_code=status, headers={"Retry-After": "5"} if status == 503 else None)(scope, receive, send)
        if not self.slots.acquire(blocking=False):
            return await fail(503, "Export capacity is busy.")
        try:
            headers = dict(scope["headers"])
            try:
                length = int(headers.get(b"content-length", b"0"))
                if length < 0:
                    raise ValueError
            except ValueError:
                return await fail(400, "Invalid export request.")
            if length > MAX_BODY:
                return await fail(413, "Export request is too large.")
            body = bytearray()
            deadline = asyncio.get_running_loop().time() + 15
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                try:
                    message = await asyncio.wait_for(receive(), timeout=max(remaining, 0))
                except TimeoutError:
                    return await fail(408, "Export request timed out.")
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > MAX_BODY:
                    return await fail(413, "Export request is too large.")
                if not message.get("more_body", False):
                    break
            delivered = False
            async def buffered():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            await self.app(scope, buffered, send)
        finally:
            self.slots.release()


class PrivateExportHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def private(message):
            if message["type"] == "http.response.start":
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"cache-control"]
                headers.extend([(b"cache-control", b"private, no-store"), (b"vary", b"Authorization")])
                message = {**message, "headers": headers}
            await send(message)
        if scope["type"] == "http" and scope.get("path", "").startswith("/api/v1/exports"):
            return await self.app(scope, receive, private)
        return await self.app(scope, receive, send)
