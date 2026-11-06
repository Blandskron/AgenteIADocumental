from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.library_repository_pg import LibraryRepositoryPg
from test_library_integrity import document, folder


@pytest.fixture
def library(migrated_database):
    engine = migrated_database
    with engine.begin() as connection:
        for name in ("a", "b", "c"):
            folder(connection, name)
        folder(connection, "foreign", owner="43")
        identifier = document(connection)
    return engine, identifier


def call(session, identifier, action, owner=42):
    repository = LibraryRepositoryPg(session, {"user_id": owner, "is_superuser": True})
    method, *args = action
    return getattr(repository, method)(*(identifier if arg == "$doc" else arg for arg in args))


def concurrent(engine, first, second, *, blocked=True):
    """Hold the first transaction at commit; prove the second really waits in PostgreSQL."""
    ready, release, started = Event(), Event(), Event()
    second_pid = []

    def run_first():
        with Session(engine) as session:
            session.execute(text("SET statement_timeout='8s'"))
            commit = session.commit

            def paused_commit():
                ready.set()
                assert release.wait(6), "Test did not release first transaction"
                commit()

            session.commit = paused_commit
            return first(session)

    def run_second():
        with Session(engine) as session:
            session.execute(text("SET statement_timeout='8s'"))
            second_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            return second(session)

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(run_first)
        try:
            assert ready.wait(4), "First operation failed before commit"
            two = pool.submit(run_second)
            assert started.wait(2)
            if blocked:
                deadline = monotonic() + 3
                with engine.connect() as observer:
                    while not observer.scalar(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": second_pid[0]}):
                        assert not two.done(), "Second transaction bypassed serialization"
                        assert monotonic() < deadline, "No database lock observed"
                        sleep(0.01)
            else:
                assert two.result(timeout=3) is True
        finally:
            release.set()
        return one.result(timeout=4), two.result(timeout=4)


def associations(engine, identifier, owner="42"):
    with engine.connect() as connection:
        return connection.scalars(text("SELECT folder_id FROM document_folder_items WHERE document_id=:id AND owner_user_id=:owner ORDER BY folder_id"),
                                  {"id": identifier, "owner": owner}).all()


@pytest.mark.parametrize("action", [
    ("add_favorite", "$doc"),
    ("add_document_to_folder", "a", "$doc"),
])
def test_concurrent_retries_create_one_marker(library, action):
    engine, identifier = library
    def operation(session):
        return call(session, identifier, action)
    assert concurrent(engine, operation, operation) == (True, True)
    table = "document_favorites" if action[0] == "add_favorite" else "document_folder_items"
    with engine.connect() as connection:
        assert connection.scalar(text(f"SELECT count(*) FROM {table} WHERE document_id=:id"), {"id": identifier}) == 1


@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("destination", ["b", None])
def test_moves_replace_all_personal_links_in_serial_order(library, initial, destination):
    engine, identifier = library
    with Session(engine) as session:
        assert call(session, identifier, ("add_document_to_folder", "foreign", "$doc"), owner=43)
        if initial:
            assert call(session, identifier, ("add_document_to_folder", "c", "$doc"))
    assert concurrent(engine,
                      lambda s: call(s, identifier, ("move_document_to_folder", "$doc", "a")),
                      lambda s: call(s, identifier, ("move_document_to_folder", "$doc", destination))) == (True, True)
    assert associations(engine, identifier) == ([] if destination is None else [destination])
    assert associations(engine, identifier, "43") == ["foreign"]


@pytest.mark.parametrize("first,second,expected", [
    (("move_document_to_folder", "$doc", "a"), ("add_document_to_folder", "b", "$doc"), ["a", "b"]),
    (("add_document_to_folder", "a", "$doc"), ("move_document_to_folder", "$doc", "b"), ["b"]),
    (("add_document_to_folder", "a", "$doc"), ("remove_document_from_folder", "a", "$doc"), []),
    (("move_document_to_folder", "$doc", "a"), ("remove_document_from_folder", "a", "$doc"), []),
    (("remove_document_from_folder", "a", "$doc"), ("add_document_to_folder", "a", "$doc"), ["a"]),
])
def test_add_move_remove_follow_commit_order(library, first, second, expected):
    engine, identifier = library
    with Session(engine) as session:
        call(session, identifier, ("add_document_to_folder", "a", "$doc"))
    assert concurrent(engine, lambda s: call(s, identifier, first), lambda s: call(s, identifier, second)) == (True, True)
    assert associations(engine, identifier) == expected


@pytest.mark.parametrize("first,second,remaining", [
    ("add_favorite", "remove_favorite", 0),
    ("remove_favorite", "add_favorite", 1),
    ("remove_favorite", "remove_favorite", 0),
])
def test_favorite_changes_follow_commit_order(library, first, second, remaining):
    engine, identifier = library
    with Session(engine) as session:
        call(session, identifier, ("add_favorite", "$doc"))
    result = concurrent(engine, lambda s: call(s, identifier, (first, "$doc")), lambda s: call(s, identifier, (second, "$doc")))
    assert result == (True, second != "remove_favorite" or first != "remove_favorite")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_favorites WHERE document_id=:id"), {"id": identifier}) == remaining


def test_different_users_do_not_share_organization_lock(library):
    engine, identifier = library
    assert concurrent(engine,
                      lambda s: call(s, identifier, ("move_document_to_folder", "$doc", "a")),
                      lambda s: call(s, identifier, ("move_document_to_folder", "$doc", "foreign"), owner=43), blocked=False) == (True, True)
    assert associations(engine, identifier) == ["a"]
    assert associations(engine, identifier, "43") == ["foreign"]


@pytest.mark.parametrize("target", ["folder", "document"])
@pytest.mark.parametrize("delete_first", [False, True])
def test_concurrent_deletion_has_no_dangling_links(library, target, delete_first):
    engine, identifier = library

    def deletion(session):
        if target == "folder":
            return call(session, identifier, ("delete_folder", "a"))
        session.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": identifier})
        session.commit()
        return True

    def addition(session):
        return call(session, identifier, ("add_document_to_folder", "a", "$doc"))
    if delete_first:
        assert concurrent(engine, deletion, addition) == (True, False)
    else:
        assert concurrent(engine, addition, deletion) == (True, True)
    assert associations(engine, identifier) == []
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": identifier}) == (target == "folder")


def test_failed_move_rolls_back_and_releases_lock(library, monkeypatch):
    engine, identifier = library
    with Session(engine) as session:
        repository = LibraryRepositoryPg(session, {"user_id": 42})
        assert repository.add_document_to_folder("a", identifier)
        original = repository._insert_folder_item

        def fail(*args):
            raise RuntimeError("Synthetic failure after removal")

        monkeypatch.setattr(repository, "_insert_folder_item", fail)
        with pytest.raises(RuntimeError, match="Synthetic failure"):
            repository.move_document_to_folder(identifier, "b")
        assert associations(engine, identifier) == ["a"]
        with Session(engine) as independent:
            independent.execute(text("SET lock_timeout='1s'"))
            assert call(independent, identifier, ("move_document_to_folder", "$doc", "c"))
        monkeypatch.setattr(repository, "_insert_folder_item", original)
        assert repository.move_document_to_folder(identifier, "b")
    assert associations(engine, identifier) == ["b"]


def test_rejected_move_keeps_previous_links_and_releases_lock(library):
    engine, identifier = library
    with Session(engine) as session:
        repository = LibraryRepositoryPg(session, {"user_id": 42})
        assert repository.add_document_to_folder("a", identifier)
        assert not repository.move_document_to_folder(identifier, "foreign")
        assert associations(engine, identifier) == ["a"]
        with Session(engine) as independent:
            independent.execute(text("SET lock_timeout='1s'"))
            assert call(independent, identifier, ("move_document_to_folder", "$doc", "b"))


def test_same_user_can_organize_other_document_while_move_is_open(library):
    engine, identifier = library
    with engine.begin() as connection:
        other = document(connection)
    assert concurrent(engine,
                      lambda s: call(s, identifier, ("move_document_to_folder", "$doc", "a")),
                      lambda s: call(s, other, ("move_document_to_folder", "$doc", "b")), blocked=False) == (True, True)


@pytest.mark.parametrize("delete_first", [False, True])
def test_ancestor_delete_and_move_preserve_consistent_order(library, delete_first):
    engine, identifier = library
    with engine.begin() as connection:
        folder(connection, "child", parent="a")
    with Session(engine) as session:
        assert call(session, identifier, ("add_document_to_folder", "a", "$doc"))
        assert call(session, identifier, ("add_document_to_folder", "child", "$doc"))

    def move(session):
        return call(session, identifier, ("move_document_to_folder", "$doc", "child"))

    def deletion(session):
        return call(session, identifier, ("delete_folder", "a"))

    assert concurrent(engine, deletion if delete_first else move, move if delete_first else deletion) == (True, not delete_first)
    assert associations(engine, identifier) == []
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": identifier}) == 1


@pytest.mark.parametrize("delete_first", [False, True])
def test_favorite_and_document_delete_are_consistent(library, delete_first):
    engine, identifier = library

    def deletion(session):
        session.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": identifier})
        session.commit()
        return True

    def addition(session):
        return call(session, identifier, ("add_favorite", "$doc"))

    assert concurrent(engine, deletion if delete_first else addition, addition if delete_first else deletion) == (True, not delete_first)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_favorites WHERE document_id=:id"), {"id": identifier}) == 0


def test_commit_failure_restores_links_and_session(library, monkeypatch):
    engine, identifier = library
    with Session(engine) as session:
        repository = LibraryRepositoryPg(session, {"user_id": 42})
        assert repository.add_document_to_folder("a", identifier)
        commit = session.commit

        def fail():
            raise RuntimeError("Synthetic commit failure")

        monkeypatch.setattr(session, "commit", fail)
        with pytest.raises(RuntimeError, match="Synthetic commit"):
            repository.move_document_to_folder(identifier, "b")
        assert associations(engine, identifier) == ["a"]
        monkeypatch.setattr(session, "commit", commit)
        assert repository.move_document_to_folder(identifier, "c")


def test_double_folder_delete_reports_actual_removal(library):
    engine, identifier = library
    deletion = ("delete_folder", "a")
    assert concurrent(engine, lambda s: call(s, identifier, deletion), lambda s: call(s, identifier, deletion)) == (True, False)
