from pathlib import Path


SQL_ROOT = Path("/database-scripts")
MIGRATION = SQL_ROOT / "migrations/002_library_integrity.sql"


def sql_source(path, *, legacy=False):
    path = Path(path)
    if legacy and path.resolve() == MIGRATION.resolve():
        return ""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("\\ir "):
            lines.append(sql_source(path.parent / line.strip()[4:], legacy=legacy))
        else:
            lines.append(line)
    return "\n".join(lines)


def execute_script(connection, path, *, legacy=False):
    connection.connection.driver_connection.execute(sql_source(path, legacy=legacy)).close()


def migrate(engine):
    with engine.begin() as connection:
        execute_script(connection, MIGRATION)
