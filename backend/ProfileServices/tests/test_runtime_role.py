import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.main import create_app
from tests.test_avatars import image_bytes, upload


@pytest.mark.parametrize("statement", [
    "SELECT password FROM public.auth_user",
    "SELECT count(*) FROM public.documents",
    "UPDATE public.auth_user SET is_active=FALSE WHERE FALSE",
    "UPDATE public.user_profiles SET user_id='forbidden' WHERE FALSE",
    "UPDATE public.user_profiles SET profile_id='forbidden' WHERE FALSE",
    "UPDATE public.user_profiles SET created_at=NOW() WHERE FALSE",
    "DELETE FROM public.user_profiles WHERE FALSE",
    "TRUNCATE public.user_profiles",
    "CREATE TABLE public.forbidden_profile_role_test (id int)",
])
def test_runtime_cannot_read_identity_or_mutate_other_resources(db_session, statement):
    db_session.execute(text("SET LOCAL ROLE profile_runtime"))
    assert db_session.scalar(text("SELECT current_user")) == "profile_runtime"
    nested = db_session.begin_nested()
    try:
        with pytest.raises(DBAPIError) as error:
            db_session.execute(text(statement))
        assert error.value.orig.sqlstate == "42501"
    finally:
        nested.rollback()


def test_http_owner_contract_works_with_runtime_role(client, db_session, token_headers, other_id):
    db_session.execute(text("SET LOCAL ROLE profile_runtime"))
    owner, other = token_headers(), token_headers(user_id=int(other_id))
    assert client.get("/api/v1/profile", headers=owner).json()["version"] == 0
    assert client.put("/api/v1/profile", headers=owner, json={"expected_version": 0, "email": "synthetic@example.com"}).status_code == 200
    saved = upload(client, owner, image_bytes(), version=1)
    assert saved.status_code == 200
    path = saved.json()["profile_picture_url"]
    assert client.get(path, headers=owner).status_code == 200
    assert client.get(path, headers=other).status_code == 404
    assert client.request("DELETE", "/api/v1/profile/avatar", headers=owner, json={"expected_version": 2}).status_code == 200
    assert client.get(path, headers=owner).status_code == 404


def test_password_login_and_startup_use_the_actual_runtime_role(committed_engine, settings, token_headers):
    runtime_url = make_url(settings.database_url).set(username="profile_runtime", password=os.environ["PROFILE_TEST_RUNTIME_PASSWORD"])
    configured = settings.model_copy(update={"database_url": runtime_url.render_as_string(hide_password=False)})
    engine = create_engine(runtime_url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_user")) == "profile_runtime"
            # SET ROLE is checked against session_user, so this must use a real login,
            # not a superuser connection temporarily executing SET LOCAL ROLE.
            for role in ("profile_identity_owner", "postgres"):
                nested = connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as error:
                        connection.execute(text("SET ROLE " + role))
                    assert error.value.orig.sqlstate == "42501"
                finally:
                    nested.rollback()
        with TestClient(create_app(configured)) as client:
            assert client.get("/api/v1/health/db").status_code == 200
            saved = upload(client, token_headers())
            assert saved.status_code == 200
            assert client.get(saved.json()["profile_picture_url"], headers=token_headers()).status_code == 200
    finally:
        engine.dispose()


@pytest.mark.parametrize("grant", [
    "GRANT SELECT (email) ON public.auth_user TO profile_runtime",
    "GRANT DELETE ON public.user_profiles TO profile_runtime",
    "GRANT UPDATE (user_id) ON public.user_profiles TO profile_runtime",
    "GRANT profile_identity_owner TO profile_runtime",
    "GRANT EXECUTE ON FUNCTION public.profile_identity_is_current(bigint,text) TO PUBLIC",
])
def test_permission_drift_is_detected_and_rolled_back(db_session, grant):
    verification = Path("/profile-db/verify_role.sql").read_text()
    db_session.execute(text(verification))
    nested = db_session.begin_nested()
    try:
        db_session.execute(text(grant))
        with pytest.raises(DBAPIError):
            db_session.execute(text(verification))
    finally:
        nested.rollback()
    db_session.execute(text(verification))
