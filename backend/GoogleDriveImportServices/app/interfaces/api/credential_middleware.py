import asyncio

from starlette.responses import JSONResponse


class CredentialMiddleware:
    """Bound only small OAuth control requests; media limits belong to ingestion."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/google-drive/"):
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store, private"), (b"referrer-policy", b"no-referrer")]
            await send(message)

        if scope["method"] == "POST" and scope["path"].endswith(("/auth-url", "/oauth/callback", "/disconnect")):
            chunks = []
            size = 0
            try:
                async with asyncio.timeout(15):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        data = message.get("body", b"")
                        size += len(data)
                        if size > 16384:
                            return await JSONResponse({"detail": "OAuth request is too large."}, 413)(scope, receive, private_send)
                        chunks.append(data)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await JSONResponse({"detail": "OAuth request timed out."}, 408)(scope, receive, private_send)
            delivered = False

            async def body():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

            return await self.app(scope, body, private_send)
        return await self.app(scope, receive, private_send)
