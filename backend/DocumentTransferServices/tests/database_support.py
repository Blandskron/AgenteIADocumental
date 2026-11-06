from pathlib import Path


SQL_ROOT = Path("/database-scripts")


def sql_source(path):
    path = Path(path)
    return "\n".join(sql_source(path.parent / line.strip()[4:]) if line.strip().startswith("\\ir ") else line
                     for line in path.read_text(encoding="utf-8").splitlines())


def execute_script(connection, path):
    connection.connection.driver_connection.execute(sql_source(path)).close()
