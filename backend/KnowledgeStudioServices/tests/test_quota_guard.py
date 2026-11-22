from datetime import date

from app.application.quota_guard import QuotaExceededError, StudioQuotaGuard


def test_quota_guard_enforces_concurrency_daily_budget_and_day_rollover():
    guard = StudioQuotaGuard(daily_token_limit=1000, max_concurrent_jobs=2)
    day1 = date(2026, 11, 21)
    day2 = date(2026, 11, 22)

    guard.acquire_job_slot("t1", estimated_tokens=400, today=day1)
    guard.acquire_job_slot("t1", estimated_tokens=400, today=day1)

    try:
        guard.acquire_job_slot("t1", estimated_tokens=100, today=day1)
        raise AssertionError("Expected CONCURRENCY_LIMIT")
    except QuotaExceededError as exc:
        assert exc.code == "CONCURRENCY_LIMIT"

    guard.release_job_slot("t1", actual_tokens=800, today=day1)
    guard.release_job_slot("t1", actual_tokens=150, today=day1)
    assert guard.remaining_tokens("t1", today=day1) == 50

    try:
        guard.acquire_job_slot("t1", estimated_tokens=100, today=day1)
        raise AssertionError("Expected DAILY_TOKEN_QUOTA")
    except QuotaExceededError as exc:
        assert exc.code == "DAILY_TOKEN_QUOTA"

    # Next day resets the quota cleanly
    assert guard.remaining_tokens("t1", today=day2) == 1000
    guard.acquire_job_slot("t1", estimated_tokens=500, today=day2)

