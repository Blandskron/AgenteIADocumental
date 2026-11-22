from __future__ import annotations

import pytest

from app.application.rate_limiter import AgentRateLimiter, RateLimitExceededError


def test_rate_limiter_enforces_sliding_window_and_recovers_after_window() -> None:
    limiter = AgentRateLimiter(max_requests=2, window_seconds=60.0)

    assert limiter.check_and_record(tenant_id="t1", user_id="u1", now=100.0) == 1
    assert limiter.check_and_record(tenant_id="t1", user_id="u1", now=110.0) == 0

    # 3rd request within window is rejected with Retry-After
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check_and_record(tenant_id="t1", user_id="u1", now=120.0)
    assert exc_info.value.retry_after_seconds >= 40

    # Different user in same tenant is unaffected
    assert limiter.check_and_record(tenant_id="t1", user_id="u2", now=120.0) == 1

    # After sliding window passes (161.0 > 100.0 + 60.0), slot opens again
    assert limiter.check_and_record(tenant_id="t1", user_id="u1", now=161.0) == 0
