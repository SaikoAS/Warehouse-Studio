"""CSV source, ordered preparation and saved result within one project."""

import base64
import csv
from decimal import Decimal
from io import StringIO
from itertools import chain
import json
import re


MAX_SOURCE_BYTES = 1024 * 1024
MAX_COLUMNS = 64
MAX_HEADER_LENGTH = 120
MAX_CELL_LENGTH = 4096
MAX_STEPS = 20
PAGE_SIZE = 50
DECIMAL_PATTERNS = {
    "de-DE": re.compile(r"[+-]?[0-9]+(?:,[0-9]+)?"),
    "en-US": re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?"),
}


def records(text):
    reader = csv.reader(StringIO(text, newline=""), delimiter=";", strict=True)
    while True:
        line = reader.line_num + 1
        try:
            cells = next(reader)
        except StopIteration:
            return
        except csv.Error as error:
            raise ValueError(f"Invalid CSV at line {line}: {error}.") from error
        if cells:
            yield line, cells


def header_names(cells):
    names = [cell.strip() for cell in cells]
    if (not 1 <= len(names) <= MAX_COLUMNS or len(set(names)) != len(names)
            or any(not 1 <= len(name) <= MAX_HEADER_LENGTH for name in names)):
        raise ValueError(f"Use up to {MAX_COLUMNS} unique, non-empty column names (up to {MAX_HEADER_LENGTH} characters each).")
    return names


def read_csv(source, custom_headers):
    try:
        rows = records(source.decode("utf-8-sig"))
    except UnicodeDecodeError as error:
        raise ValueError("Save the CSV as UTF-8 and try again.") from error
    first = next(rows, None)
    if first is None:
        raise ValueError("The CSV has no records.")
    if custom_headers is None:
        names = header_names(first[1])
    else:
        names = custom_headers
        rows = chain((first,), rows)

    parsed = []
    for line, cells in rows:
        if len(cells) != len(names):
            raise ValueError(f"CSV line {line} has {len(cells)} fields. Expected {len(names)}.")
        if any(len(cell) > MAX_CELL_LENGTH for cell in cells):
            raise ValueError(f"CSV line {line} has a field longer than {MAX_CELL_LENGTH} characters.")
        parsed.append((line, cells))
    return {"columns": [{"name": name, "type": "text"} for name in names], "rows": parsed}


def execute_steps(table, steps, through=None):
    if not isinstance(steps, list) or len(steps) > MAX_STEPS:
        raise ValueError(f"Use at most {MAX_STEPS} preparation steps.")
    if through is not None:
        if type(through) is not int or not 0 <= through < len(steps):
            raise ValueError("Select a step to preview.")
        steps = steps[:through + 1]
    columns, rows = table["columns"], table["rows"]
    original_names = [column["name"] for column in columns]
    for number, step in enumerate(steps, 1):
        index = step.get("column") if isinstance(step, dict) else None
        if type(index) is not int or not 0 <= index < len(columns):
            raise ValueError(f"Step {number}: choose a source column.")
        column = columns[index]
        match step.get("operation"):
            case "rename":
                name = step.get("name")
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_HEADER_LENGTH:
                    raise ValueError(f"Step {number}: enter a column name (up to {MAX_HEADER_LENGTH} characters).")
                name = name.strip()
                if any(other["name"] == name for other in columns if other is not column):
                    raise ValueError(f"Step {number}: the column name {name!r} is already in use.")
                column["name"] = name
            case "filter":
                value, mode = step.get("value"), step.get("mode")
                if not isinstance(value, str) or len(value) > MAX_CELL_LENGTH or mode not in ("keep", "remove"):
                    raise ValueError(f"Step {number}: choose a filter and enter a value of up to {MAX_CELL_LENGTH} characters.")
                keep_matches = mode == "keep"
                rows = [(line, cells) for line, cells in rows if (cells[index] == value) == keep_matches]
            case "convert":
                target = step.get("target")
                if target not in ("text", "decimal"):
                    raise ValueError(f"Step {number}: choose Text or Decimal.")
                if target == "decimal":
                    locale = step.get("locale")
                    if not isinstance(locale, str) or locale not in DECIMAL_PATTERNS:
                        raise ValueError(f"Step {number}: choose a decimal locale.")
                    if column["type"] == "text":
                        for line, cells in rows:
                            value = cells[index].strip()
                            if not DECIMAL_PATTERNS[locale].fullmatch(value):
                                raise ValueError(f"Step {number}: invalid decimal at CSV line {line}, column {index + 1} ({original_names[index]}).")
                            cells[index] = format(Decimal(value.replace(",", ".")), "f")
                column["type"] = target
            case _:
                raise ValueError(f"Step {number}: choose a preparation operation.")
    return {"columns": columns, "rows": rows}


def saved_workflow(db, fields="*"):
    # Projects created before CSV preparation have the same metadata schema.
    if db.execute("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'csv_workflow'").fetchone():
        return db.execute(f"SELECT {fields} FROM csv_workflow WHERE singleton = 1").fetchone()
    return None


def state(db, _request=None):
    row = saved_workflow(db, "name, length(source) AS bytes, revision, columns, steps, result IS NOT NULL AS has_result")
    source = None if row is None else {
        "name": row["name"], "bytes": row["bytes"], "revision": row["revision"],
        "columns": json.loads(row["columns"]), "steps": json.loads(row["steps"]),
        "hasResult": bool(row["has_result"]),
    }
    return {"maxBytes": MAX_SOURCE_BYTES, "maxSteps": MAX_STEPS, "source": source}


def import_source(db, request):
    if saved_workflow(db, "singleton") is not None:
        raise ValueError("A CSV is already saved in this project. Reload saved preparation to see it.")
    name, encoded, custom = request.get("name"), request.get("content"), request.get("headers")
    if not isinstance(name, str) or not 1 <= len(name) <= 255 or not isinstance(encoded, str):
        raise ValueError("Choose a CSV file.")
    try:
        source = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("The upload could not be read. Choose the CSV file again.") from error
    if len(source) > MAX_SOURCE_BYTES:
        raise ValueError(f"Choose a CSV of at most {MAX_SOURCE_BYTES:,} bytes (1 MiB).")
    if custom is not None:
        if not isinstance(custom, str) or len(custom) > 16_384:
            raise ValueError("Enter custom column names in one semicolon-separated record.")
        entered = list(records(custom))
        if len(entered) != 1:
            raise ValueError("Enter custom column names in one semicolon-separated record.")
        custom = header_names(entered[0][1])
    table = read_csv(source, custom)
    db.execute("""CREATE TABLE IF NOT EXISTS csv_workflow (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1), name TEXT NOT NULL,
        source BLOB NOT NULL, custom_headers TEXT NOT NULL, columns TEXT NOT NULL,
        steps TEXT NOT NULL, result TEXT, revision INTEGER NOT NULL
    )""")
    db.execute("INSERT INTO csv_workflow VALUES (1, ?, ?, ?, ?, '[]', NULL, 1)", (
        name, source, json.dumps(custom), json.dumps(table["columns"]),
    ))
    return state(db)


def workflow(db, revision, fields):
    row = saved_workflow(db, fields)
    if row is None:
        raise ValueError("Import a CSV into this project first.")
    if type(revision) is not int or revision != row["revision"]:
        raise ValueError("Another window saved this preparation. Reload saved preparation.")
    return row


def page(db, request):
    offset = request.get("offset", 0)
    if type(offset) is not int or offset < 0:
        raise ValueError("Invalid table position.")
    revision = request.get("revision")
    match request.get("view"):
        case "source":
            row = workflow(db, revision, "revision, source, custom_headers")
            table = read_csv(row["source"], json.loads(row["custom_headers"]))
        case "preview":
            through = request.get("through")
            if type(through) is not int:
                raise ValueError("Select a step to preview.")
            row = workflow(db, revision, "revision, source, custom_headers")
            source = read_csv(row["source"], json.loads(row["custom_headers"]))
            table = execute_steps(source, request.get("steps"), through)
        case "result":
            row = workflow(db, revision, "revision, result")
            if row["result"] is None:
                raise ValueError("Apply preparation steps to save a result first.")
            table = json.loads(row["result"])
        case _:
            raise ValueError("Choose a table to view.")
    rows = table["rows"]
    return {"columns": table["columns"], "rows": rows[offset:offset + PAGE_SIZE], "total": len(rows), "pageSize": PAGE_SIZE}


def apply(db, request):
    row = workflow(db, request.get("revision"), "revision, source, custom_headers")
    steps = request.get("steps")
    table = execute_steps(read_csv(row["source"], json.loads(row["custom_headers"])), steps)
    db.execute("UPDATE csv_workflow SET steps = ?, result = ?, revision = revision + 1 WHERE singleton = 1", (
        json.dumps(steps), json.dumps(table, separators=(",", ":")),
    ))
    return state(db)
