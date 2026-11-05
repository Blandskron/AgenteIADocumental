import asyncio

import pytest

from app.interfaces.api.body_limit import MAX_REQUEST_BYTES, RequestBodyLimit


@pytest.mark.parametrize("sizes,allowed", [
    ([MAX_REQUEST_BYTES], True), ([MAX_REQUEST_BYTES + 1], False),
    ([MAX_REQUEST_BYTES // 2, MAX_REQUEST_BYTES // 2], True),
    ([MAX_REQUEST_BYTES // 2, MAX_REQUEST_BYTES // 2 + 1], False),
])
def test_body_limit_counts_actual_streamed_bytes(sizes, allowed):
    async def exercise():
        messages = [{"type": "http.request", "body": b"x" * size, "more_body": index < len(sizes) - 1}
                    for index, size in enumerate(sizes)]
        sent, bodies = [], []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            bodies.append((await receive())["body"])

        # A small claimed content-length must not bypass the actual byte budget.
        await RequestBodyLimit(app)({"type": "http", "method": "POST", "headers": [(b"content-length", b"1")]}, receive, send)
        if allowed:
            assert bodies == [b"x" * sum(sizes)]
        else:
            assert bodies == []
            assert sent[0]["status"] == 413

    asyncio.run(exercise())


def test_disconnected_body_does_not_run_application():
    async def exercise():
        async def receive():
            return {"type": "http.disconnect"}

        async def forbidden(*args):
            pytest.fail("Disconnected request reached the application")

        await RequestBodyLimit(forbidden)({"type": "http", "method": "POST"}, receive, forbidden)

    asyncio.run(exercise())
