from starlette.responses import JSONResponse


MAX_REQUEST_BYTES = 65_536


class RequestBodyLimit:
    """Bound buffered request bodies before FastAPI decodes submitted JSON."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_REQUEST_BYTES:
                await JSONResponse(status_code=413, content={"detail": "Request body exceeds 65536 bytes."})(scope, receive, send)
                return
            if chunk:
                chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        async def replay():
            nonlocal body
            if body is not None:
                message = {"type": "http.request", "body": body, "more_body": False}
                body = None
                return message
            return await receive()

        await self.app(scope, replay, send)
