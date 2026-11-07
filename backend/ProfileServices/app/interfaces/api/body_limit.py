import json

from starlette.responses import JSONResponse


MAX_PROFILE_BYTES = 65536
MAX_AVATAR_REQUEST_BYTES = 5 * 1024 * 1024 + 65536


class ProfileBodyLimit:
    """Bound JSON profile writes before parsing; avatar multipart is handled separately."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        if root and path.startswith(root + "/"):
            path = path[len(root):]
        avatar = path == "/api/v1/profile/upload" and scope.get("method") == "POST"
        profile = path == "/api/v1/profile" and scope.get("method") == "PUT"
        clear = path == "/api/v1/profile/avatar" and scope.get("method") == "DELETE"
        if scope["type"] != "http" or not (avatar or profile or clear):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > (MAX_AVATAR_REQUEST_BYTES if avatar else MAX_PROFILE_BYTES):
                return await JSONResponse(status_code=413, content={"detail": "Profile request exceeds allowed size."})(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        try:
            parsed = {} if avatar else json.loads(body)
            pending, nodes = [(parsed, 0)], 0
            while pending:
                value, depth = pending.pop()
                nodes += 1
                if depth > 16 or nodes > 2048:
                    raise ValueError("Profile JSON exceeds structural limits.")
                if isinstance(value, (dict, list)):
                    children = value.values() if isinstance(value, dict) else value
                    if len(value) > 2048:
                        raise ValueError("Profile JSON exceeds structural limits.")
                    pending.extend((child, depth + 1) for child in children)
        except (ValueError, UnicodeError, RecursionError):
            return await JSONResponse(status_code=400, content={"detail": "Invalid profile JSON."})(scope, receive, send)

        async def replay():
            nonlocal body
            if body is None:
                return await receive()
            value, body = body, None
            return {"type": "http.request", "body": value, "more_body": False}
        return await self.app(scope, replay, send)
