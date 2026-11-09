import json
from tempfile import SpooledTemporaryFile
from time import monotonic

import httpx

from app.shared.errors import GoogleDriveError, ProviderStatusError


class TransferBudget:
    def __init__(self, remaining):
        self.remaining = remaining

    def consume(self, amount):
        if amount > self.remaining:
            self.remaining = 0
            raise GoogleDriveError("Import transfer budget is exhausted.")
        self.remaining -= amount


def read_response(response, destination, maximum, deadline, budget=None, *, allowed_statuses=(200,)):
    if response.status_code not in allowed_statuses:
        raise ProviderStatusError(response.status_code)
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise GoogleDriveError("Unexpected provider response.")
    declared = response.headers.get("content-length")
    if declared is not None and (
        not declared.isascii()
        or not declared.isdigit()
        or len(declared) > 10
        or int(declared) > maximum
    ):
        raise GoogleDriveError("Provider response exceeds supported limits.")
    total = 0
    for chunk in response.iter_raw():
        if budget is not None:
            budget.consume(len(chunk))
        total += len(chunk)
        if total > maximum or monotonic() >= deadline:
            raise GoogleDriveError("Provider response exceeds supported limits.")
        destination.write(chunk)
    if monotonic() >= deadline or (declared is not None and total != int(declared)):
        raise GoogleDriveError("Incomplete or expired provider response.")
    destination.seek(0)
    return total


def provider_json(method, url, *, timeout, deadline=None, **kwargs):
    deadline = deadline or monotonic() + timeout
    if monotonic() >= deadline:
        raise GoogleDriveError("Provider time budget is exhausted.")
    headers = {**kwargs.pop("headers", {}), "Accept-Encoding": "identity"}
    try:
        with httpx.Client(
            timeout=min(timeout, max(0.1, deadline - monotonic())),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream(method, url, headers=headers, **kwargs) as response:
                with SpooledTemporaryFile(max_size=32768, mode="w+b") as body:
                    read_response(response, body, 32768, deadline)
                    value = json.load(body)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (httpx.HTTPError, ValueError, UnicodeError, RecursionError):
        raise GoogleDriveError(
            "Provider JSON response is unavailable or invalid."
        ) from None
