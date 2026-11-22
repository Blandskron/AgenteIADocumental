from __future__ import annotations

import pytest

from app.application.concurrency_guard import ConcurrencyLimitError, TenantConcurrencyGuard


def test_concurrency_guard_enforces_per_tenant_cap_and_releases_on_error() -> None:
    guard = TenantConcurrencyGuard(max_concurrent_per_tenant=2)

    with guard.acquire("t1") as c1:
        assert c1 == 1
        with guard.acquire("t1") as c2:
            assert c2 == 2
            with pytest.raises(ConcurrencyLimitError):
                with guard.acquire("t1"):
                    pass
            # Another tenant is completely isolated
            with guard.acquire("t2") as t2_c1:
                assert t2_c1 == 1

    assert guard.active_count("t1") == 0
    assert guard.active_count("t2") == 0

    # Releases slot cleanly even when an exception occurs inside the block
    with pytest.raises(ValueError):
        with guard.acquire("t1"):
            raise ValueError("boom")
    assert guard.active_count("t1") == 0
