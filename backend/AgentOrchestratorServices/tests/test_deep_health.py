from __future__ import annotations

from app.application.health_service import run_deep_health_check


def test_deep_health_reports_ok_and_degraded_without_leaking_secrets() -> None:
    def ok_http(url, _timeout):
        return {"status": "ok", "http_status": 200}

    ok_report = run_deep_health_check(
        agents_enabled=True,
        code_mode_enabled=True,
        mcp_base_url="http://knowledge-studio-service:8000/api/v1/mcp",
        sandbox_url="http://code-sandbox-runner:8090",
        http_transport=ok_http,
        db_probe=lambda: None,
    )
    assert ok_report["status"] == "ok"
    assert ok_report["checks"]["database"]["status"] == "ok"
    assert ok_report["checks"]["code_sandbox_runner"]["status"] == "ok"

    def bad_db():
        raise RuntimeError("Failed with Bearer secret.jwt.leak")

    degraded = run_deep_health_check(
        agents_enabled=True,
        code_mode_enabled=False,
        http_transport=ok_http,
        db_probe=bad_db,
    )
    assert degraded["status"] == "degraded"
    assert degraded["checks"]["code_sandbox_runner"]["status"] == "disabled"
    assert "secret.jwt.leak" not in degraded["checks"]["database"]["detail"]
