from uuid import uuid4

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.main import app


@pytest.fixture
def pages(configured_client, signing_key, engine):
    client, _ = configured_client
    owner, prefix = int(uuid4().hex[:12], 16), uuid4().hex
    ids = [f"{prefix}_{index:03}" for index in range(207)]
    headers = {"Authorization": "Bearer " + jwt.encode({"user_id": owner, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")}
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                session.execute(text("""
                    INSERT INTO transfer_events (transfer_id, owner_user_id, filename, direction, status)
                    VALUES (:id, :owner, 'synthetic.txt', 'UPLOAD', 'PENDING')
                """), [{"id": identifier, "owner": str(owner)} for identifier in ids]
                   + [{"id": uuid4().hex, "owner": str(owner + 1)}])
                session.commit()
                app.dependency_overrides[get_session] = lambda: session
                yield client, headers, list(reversed(ids))
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 0


def test_pages_have_stable_ties_private_rows_and_exact_terminal_page(pages):
    client, headers, expected = pages
    default = client.get("/api/v1/transfers", headers=headers).json()
    assert default["limit"] == 50 and default["offset"] == 0 and default["has_more"] is True
    assert len(default["items"]) == 50
    rows = []
    for offset in (0, 100, 200):
        response = client.get(f"/api/v1/transfers?limit=100&offset={offset}", headers=headers)
        assert response.status_code == 200
        page = response.json()
        assert set(page) == {"items", "limit", "offset", "has_more"}
        assert page["has_more"] is (offset != 200)
        rows.extend(row["transfer_id"] for row in page["items"])
    assert rows == expected
    assert client.get("/api/v1/transfers?offset=207", headers=headers).json() == {"items": [], "limit": 50, "offset": 207, "has_more": False}
    assert client.get("/api/v1/transfers?offset=10000", headers=headers).json()["items"] == []


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "offset=10001", "offset=sensitive-synthetic", "limit=sensitive-synthetic"])
def test_page_bounds_are_private(pages, query):
    client, headers, _ = pages
    response = client.get("/api/v1/transfers?" + query, headers=headers)
    assert response.status_code == 422
    assert "sensitive-synthetic" not in response.text and '"input"' not in response.text


def test_openapi_defines_page_and_bounded_offset(configured_client):
    schema = configured_client[0].get("/openapi.json").json()
    page = schema["components"]["schemas"]["TransferPage"]
    assert set(page["properties"]) == {"items", "limit", "offset", "has_more"}
    parameters = schema["paths"]["/api/v1/transfers"]["get"]["parameters"]
    offset = next(parameter for parameter in parameters if parameter["name"] == "offset")
    assert offset["schema"]["minimum"] == 0 and offset["schema"]["maximum"] == 10000
