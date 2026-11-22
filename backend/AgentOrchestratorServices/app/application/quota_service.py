"""Persistent per-tenant daily token and run quota enforcement over agents.agent_usage_daily (AG-009)."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


class QuotaExceededError(RuntimeError):
    """Raised when a tenant exceeds its daily agent token or run quota (HTTP 429)."""


class TenantQuotaService:
    """Tracks and enforces daily token/run quotas per tenant."""

    def __init__(
        self,
        *,
        session: Session | None = None,
        daily_token_quota: int | None = None,
        daily_run_quota: int | None = None,
    ) -> None:
        self._session = session
        self._daily_token_quota = (
            daily_token_quota
            if daily_token_quota is not None
            else int(os.environ.get("AGENT_DAILY_TOKEN_QUOTA", "200000"))
        )
        self._daily_run_quota = (
            daily_run_quota
            if daily_run_quota is not None
            else int(os.environ.get("AGENT_DAILY_RUN_QUOTA", "200"))
        )
        self._memory_usage: dict[tuple[str, str], dict[str, int]] = {}

    def get_usage(self, tenant_id: str, usage_day: date | None = None) -> dict[str, int]:
        day = usage_day or datetime.now(timezone.utc).date()
        if self._session is not None:
            row = self._session.execute(
                text(
                    """
                    SELECT runs_count, tokens_used
                    FROM agents.agent_usage_daily
                    WHERE tenant_id = :tenant_id AND usage_date = :usage_date
                    """
                ),
                {"tenant_id": tenant_id, "usage_date": day},
            ).mappings().first()
            if row:
                return {"runs_count": int(row["runs_count"]), "tokens_used": int(row["tokens_used"])}
            return {"runs_count": 0, "tokens_used": 0}
        return dict(self._memory_usage.get((tenant_id, day.isoformat()), {"runs_count": 0, "tokens_used": 0}))

    def check_can_start(self, tenant_id: str, *, requested_max_tokens: int = 0, usage_day: date | None = None) -> None:
        usage = self.get_usage(tenant_id, usage_day=usage_day)
        if usage["runs_count"] >= self._daily_run_quota:
            raise QuotaExceededError(
                f"Cuota diaria de ejecuciones agénticas agotada ({usage['runs_count']}/{self._daily_run_quota})."
            )
        if usage["tokens_used"] + max(0, requested_max_tokens) > self._daily_token_quota:
            raise QuotaExceededError(
                f"Cuota diaria de tokens agénticos agotada ({usage['tokens_used']}/{self._daily_token_quota})."
            )

    def consume(
        self,
        tenant_id: str,
        *,
        runs_delta: int = 0,
        tokens_delta: int = 0,
        usage_day: date | None = None,
    ) -> dict[str, int]:
        day = usage_day or datetime.now(timezone.utc).date()
        if self._session is not None:
            self._session.execute(
                text(
                    """
                    INSERT INTO agents.agent_usage_daily (tenant_id, usage_date, runs_count, tokens_used, updated_at)
                    VALUES (:tenant_id, :usage_date, :runs_delta, :tokens_delta, NOW())
                    ON CONFLICT (tenant_id, usage_date) DO UPDATE
                    SET runs_count = agents.agent_usage_daily.runs_count + EXCLUDED.runs_count,
                        tokens_used = agents.agent_usage_daily.tokens_used + EXCLUDED.tokens_used,
                        updated_at = NOW()
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "usage_date": day,
                    "runs_delta": max(0, runs_delta),
                    "tokens_delta": max(0, tokens_delta),
                },
            )
            self._session.commit()
            return self.get_usage(tenant_id, usage_day=day)

        key = (tenant_id, day.isoformat())
        current = self._memory_usage.setdefault(key, {"runs_count": 0, "tokens_used": 0})
        current["runs_count"] += max(0, runs_delta)
        current["tokens_used"] += max(0, tokens_delta)
        return dict(current)
