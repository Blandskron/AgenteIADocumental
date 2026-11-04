import json
import logging
from time import time
from unicodedata import normalize

from django.db import connection
from django.utils.crypto import salted_hmac

from .models import LoginAttemptBudget

WINDOW_SECONDS = 60
ORIGIN_LIMIT = 30
ACCOUNT_LIMIT = 8
logger = logging.getLogger("blandskron.auth.audit")


def audit_auth_event(event, **details):
    logger.info(json.dumps({"event": event, **details}))


def _consume(scope, value, window, limit):
    key = salted_hmac("auth-login-budget", f"{scope}:{value}", algorithm="sha256").hexdigest()
    table = connection.ops.quote_name(LoginAttemptBudget._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {table} (key, "window", attempts) VALUES (%s, %s, 1)
            ON CONFLICT (key) DO UPDATE SET
                "window" = EXCLUDED."window",
                attempts = CASE WHEN {table}."window" < EXCLUDED."window"
                                THEN 1 ELSE {table}.attempts + 1 END
            WHERE {table}."window" < EXCLUDED."window"
               OR ({table}."window" = EXCLUDED."window" AND {table}.attempts < %s)
            RETURNING 1
            """,
            [key, window, limit],
        )
        return cursor.fetchone() is not None


def login_retry_after(request, username):
    now = int(time())
    window = now // WINDOW_SECONDS
    origin = request.META.get("REMOTE_ADDR") or "unknown"
    account = normalize("NFKC", username).strip().casefold() if isinstance(username, str) else ""
    if _consume("origin", origin, window, ORIGIN_LIMIT) and (
        not account or _consume("account", account, window, ACCOUNT_LIMIT)
    ):
        return 0
    return WINDOW_SECONDS - now % WINDOW_SECONDS
