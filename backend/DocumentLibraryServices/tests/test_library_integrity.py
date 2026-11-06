from uuid import uuid4

import jwt
import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.main import app
from app.infrastructure.database.repositories.library_repository_pg import LibraryRepositoryPg
from app.shared.errors import NotFoundError
from database_support import SQL_ROOT, execute_script, migrate


def folder(connection, identifier, owner="42", parent=None, name=None):
    connection.execute(text("""
        INSERT INTO document_folders (folder_id, owner_user_id, parent_folder_id, name)
        VALUES (:id, :owner, :parent, :name)
    """), {"id": identifier, "owner": owner, "parent": parent, "name": name if name is not None else identifier})


def document(connection):
    identifier = uuid4().hex
    connection.execute(text("""INSERT INTO documents (document_id, filename, storage_path, mime_type, owner_user_id)
        VALUES (:id, 'synthetic.txt', 'lib004-synthetic.txt', 'text/plain', '42')"""), {"id": identifier})
    return identifier


def test_migration_repeats_and_cascades_preserve_documents(legacy_database):
    with legacy_database.begin() as connection:
        folder(connection, "root")
        folder(connection, "child", parent="root")
        folder(connection, "other", owner="43")
        identifier = document(connection)
        connection.execute(text("INSERT INTO document_folder_items VALUES ('child', :id, '42', now())"), {"id": identifier})
        connection.execute(text("INSERT INTO document_favorites VALUES (:id, '42', now())"), {"id": identifier})
    migrate(legacy_database)
    migrate(legacy_database)
    with legacy_database.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_folders")) == 3
        assert connection.scalar(text("SELECT count(*) FROM library_integrity_audit() WHERE affected > 0")) == 0
        connection.execute(text("DELETE FROM document_folders WHERE folder_id='root'"))
        assert connection.scalar(text("SELECT count(*) FROM document_folders")) == 1
        assert connection.scalar(text("SELECT count(*) FROM document_folder_items")) == 0
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": identifier}) == 1
        assert connection.scalar(text("SELECT count(*) FROM document_favorites WHERE document_id=:id"), {"id": identifier}) == 1


@pytest.mark.parametrize("problem", ["parent_owner", "item_owner", "cycle", "blank", "duplicate", "missing_parent", "missing_item_document", "missing_favorite_document"])
def test_dirty_legacy_data_stops_migration_without_removal(legacy_database, problem):
    with legacy_database.begin() as connection:
        folder(connection, "root")
        folder(connection, "other", owner="43")
        if problem == "parent_owner":
            folder(connection, "invalid", owner="42", parent="other")
        elif problem == "item_owner":
            identifier = document(connection)
            connection.execute(text("INSERT INTO document_folder_items VALUES ('root', :id, '43', now())"), {"id": identifier})
        elif problem == "cycle":
            folder(connection, "child", parent="root")
            connection.execute(text("UPDATE document_folders SET parent_folder_id='child' WHERE folder_id='root'"))
        elif problem == "blank":
            folder(connection, "invalid", name=" \t ")
        elif problem == "duplicate":
            connection.exec_driver_sql("DROP INDEX document_folders_owner_root_name_unique")
            folder(connection, "invalid", name="root")
        elif problem == "missing_parent":
            connection.exec_driver_sql("ALTER TABLE document_folders DROP CONSTRAINT document_folders_parent_folder_id_fkey")
            folder(connection, "invalid", parent="missing")
        elif problem == "missing_item_document":
            connection.exec_driver_sql("ALTER TABLE document_folder_items DROP CONSTRAINT document_folder_items_document_id_fkey")
            connection.exec_driver_sql("INSERT INTO document_folder_items VALUES ('root','missing','42',now())")
        else:
            connection.exec_driver_sql("ALTER TABLE document_favorites DROP CONSTRAINT document_favorites_document_id_fkey")
            connection.exec_driver_sql("INSERT INTO document_favorites VALUES ('missing','42',now())")
        before = connection.execute(text("SELECT folder_id, name, parent_folder_id, owner_user_id FROM document_folders ORDER BY folder_id")).all()
        items_before = connection.execute(text("SELECT folder_id, document_id, owner_user_id FROM document_folder_items")).all()
    with pytest.raises(psycopg.errors.CheckViolation, match="Library integrity preflight failed"):
        migrate(legacy_database)
    with legacy_database.begin() as connection:
        assert connection.execute(text("SELECT folder_id, name, parent_folder_id, owner_user_id FROM document_folders ORDER BY folder_id")).all() == before
        assert connection.execute(text("SELECT folder_id, document_id, owner_user_id FROM document_folder_items")).all() == items_before
        assert connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='document_folders_id_owner_key' AND conrelid='document_folders'::regclass")) == 0
        execute_script(connection, SQL_ROOT / "functions/002_library_integrity_audit.sql")
        assert connection.scalar(text("SELECT count(*) FROM library_integrity_audit() WHERE affected > 0")) > 0


@pytest.mark.parametrize("mutation", ["foreign_parent", "foreign_item", "self_parent", "multirow_cycle", "reparent", "owner", "identifier", "blank"])
def test_structural_violations_are_rejected(migrated_database, mutation):
    with migrated_database.begin() as connection:
        folder(connection, "root")
        folder(connection, "foreign", owner="43")
        identifier = document(connection)
    with pytest.raises(IntegrityError):
        with migrated_database.begin() as connection:
            if mutation == "foreign_parent":
                folder(connection, "child", parent="foreign")
            elif mutation == "foreign_item":
                connection.execute(text("INSERT INTO document_folder_items VALUES ('foreign', :id, '42', now())"), {"id": identifier})
            elif mutation == "self_parent":
                folder(connection, "self", parent="self")
            elif mutation == "multirow_cycle":
                connection.exec_driver_sql("INSERT INTO document_folders (folder_id,name,parent_folder_id,owner_user_id) VALUES ('a','a','b','42'), ('b','b','a','42')")
            elif mutation == "blank":
                folder(connection, "blank", name=" \t ")
            else:
                field, value = {"reparent": ("parent_folder_id", "foreign"), "owner": ("owner_user_id", "43"), "identifier": ("folder_id", "new")}[mutation]
                connection.execute(text(f"UPDATE document_folders SET {field}=:value WHERE folder_id='root'"), {"value": value})


def test_name_conflicts_return_409_and_session_recovers(migrated_database, configured_client, signing_key, monkeypatch):
    client, _ = configured_client
    with Session(migrated_database) as session:
        monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
        token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
        headers = {"Authorization": f"Bearer {token}"}
        first = client.post("/api/v1/folders", json={"name": "Root"}, headers=headers)
        assert first.status_code == 201
        identifier = first.json()["folder_id"]
        duplicate = client.post("/api/v1/folders", json={"name": " Root "}, headers=headers)
        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "Folder name already exists at this level."}
        child = client.post("/api/v1/folders", json={"name": "Child", "parent_folder_id": identifier}, headers=headers)
        assert child.status_code == 201
        assert client.post("/api/v1/folders", json={"name": "Child", "parent_folder_id": identifier}, headers=headers).status_code == 409
        second = client.post("/api/v1/folders", json={"name": "Second"}, headers=headers)
        assert second.status_code == 201
        assert client.patch(f"/api/v1/folders/{second.json()['folder_id']}", json={"name": "Root"}, headers=headers).status_code == 409
        assert client.post("/api/v1/folders", json={"name": "   "}, headers=headers).status_code == 422
        assert client.patch(f"/api/v1/folders/{identifier}", json={"name": "Renamed", "metadata": {"synthetic": True}}, headers=headers).status_code == 200


def test_legacy_inconsistent_association_remains_private(legacy_database, configured_client, signing_key, monkeypatch):
    client, _ = configured_client
    with legacy_database.begin() as connection:
        folder(connection, "foreign", owner="43")
        identifier = document(connection)
        connection.execute(text("INSERT INTO document_folder_items VALUES ('foreign', :id, '42', now())"), {"id": identifier})
    with Session(legacy_database) as session:
        monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
        token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
        response = client.get("/api/v1/folders/foreign/documents", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 404


def test_parent_deleted_after_precheck_returns_not_found_and_rolls_back(migrated_database, monkeypatch):
    with migrated_database.begin() as connection:
        folder(connection, "parent")
    with Session(migrated_database) as session:
        repository = LibraryRepositoryPg(session, {"user_id": 42})
        original = repository._folder

        def disappearing(identifier):
            result = original(identifier)
            with migrated_database.begin() as connection:
                connection.execute(text("DELETE FROM document_folders WHERE folder_id=:id"), {"id": identifier})
            return result

        monkeypatch.setattr(repository, "_folder", disappearing)
        with pytest.raises(NotFoundError, match="Parent folder not found"):
            repository.create_folder("Child", "parent")
        assert session.scalar(text("SELECT count(*) FROM document_folders")) == 0
        assert repository.create_folder("Recovery").name == "Recovery"
