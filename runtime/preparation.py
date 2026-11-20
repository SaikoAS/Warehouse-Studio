"""CSV source, ordered preparation and saved result within one project."""

from decimal import Decimal
from itertools import islice
import json
import re
from uuid import uuid4

from runtime import csv_source
from runtime.csv_source import MAX_CELL_LENGTH, MAX_HEADER_LENGTH
MAX_STEPS = 20
PAGE_SIZE = 50
DECIMAL_PATTERNS = {
    "de-DE": re.compile(r"[+-]?[0-9]+(?:,[0-9]+)?"),
    "en-US": re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?"),
}


def filter_text(value):
    # The HTML textarea presents all line breaks as LF. Apply that rule only to comparisons.
    return value.replace("\r\n", "\n").replace("\r", "\n")


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
                expected = filter_text(value)
                rows = [(line, cells) for line, cells in rows if (filter_text(cells[index]) == expected) == keep_matches]
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


def import_details(db):
    if db.execute("SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'csv_import_details'").fetchone():
        row = db.execute("SELECT source_id, encoding, delimiter, column_metadata FROM csv_import_details WHERE singleton = 1").fetchone()
        if row is not None:
            return dict(row)
    # A v0.1.1 project has one immutable source. Its project ID gives that source a stable reference.
    project_id = db.execute("SELECT id FROM project WHERE singleton = 1").fetchone()["id"]
    return {"source_id": project_id, "encoding": "utf-8", "delimiter": ";", "column_metadata": None}


def source_table(row, details):
    return csv_source.table(csv_source.decode(row["source"], details["encoding"]), details["delimiter"],
                            json.loads(row["custom_headers"]))


def column_metadata(names, samples, assigned):
    return [{"position": index + 1, "originalName": name, "assigned": assigned,
             "samples": [cells[index] for _, cells in samples]} for index, name in enumerate(names)]


def state(db, _request=None):
    row = saved_workflow(db, "name, length(source) AS bytes, revision, columns, steps, custom_headers, result IS NOT NULL AS has_result")
    source = None
    if row is not None:
        details = import_details(db)
        assigned = json.loads(row["custom_headers"]) is not None
        if details["column_metadata"] is None:
            _, names, rows = source_table(saved_workflow(db, "source, custom_headers"), details)
            metadata = column_metadata(names, list(islice(rows, 3)), assigned)
        else:
            metadata = json.loads(details["column_metadata"])
        source = {
            "id": details["source_id"], "name": row["name"], "bytes": row["bytes"], "revision": row["revision"],
            "columns": json.loads(row["columns"]), "steps": json.loads(row["steps"]),
            "columnMetadata": metadata, "hasResult": bool(row["has_result"]),
            "importOptions": {"encoding": details["encoding"], "delimiter": details["delimiter"], "hasHeader": not assigned},
        }
    return {"maxBytes": csv_source.MAX_SOURCE_BYTES, "maxPreviewBytes": csv_source.MAX_PREVIEW_BYTES,
            "maxCellLength": MAX_CELL_LENGTH, "maxSteps": MAX_STEPS, "source": source}


def import_source(db, request):
    if saved_workflow(db, "singleton") is not None:
        raise ValueError("A CSV is already saved in this project. Reload saved preparation to see it.")
    name, source = csv_source.upload(request, csv_source.MAX_SOURCE_BYTES)
    encoding = csv_source.option(request, "encoding", csv_source.ENCODINGS, "utf-8")
    delimiter = csv_source.option(request, "delimiter", csv_source.DELIMITERS, ";")
    if encoding is None or delimiter is None:
        raise ValueError("Confirm the CSV encoding and delimiter before importing.")
    custom = csv_source.custom_headers(request.get("headers"), delimiter)
    columns, names, rows = csv_source.table(csv_source.decode(source, encoding), delimiter, custom)
    samples = list(islice(rows, 3))
    for _ in rows:
        pass  # Validate every record before writing anything to the project.
    db.execute("""CREATE TABLE IF NOT EXISTS csv_workflow (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1), name TEXT NOT NULL,
        source BLOB NOT NULL, custom_headers TEXT NOT NULL, columns TEXT NOT NULL,
        steps TEXT NOT NULL, result TEXT, revision INTEGER NOT NULL
    )""")
    db.execute("INSERT INTO csv_workflow VALUES (1, ?, ?, ?, ?, '[]', NULL, 1)", (
        name, source, json.dumps(custom), json.dumps(columns),
    ))
    db.execute("""CREATE TABLE csv_import_details (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1), source_id TEXT NOT NULL,
        encoding TEXT NOT NULL, delimiter TEXT NOT NULL, column_metadata TEXT NOT NULL
    )""")
    db.execute("INSERT INTO csv_import_details VALUES (1, ?, ?, ?, ?)", (
        uuid4().hex, encoding, delimiter, json.dumps(column_metadata(names, samples, custom is not None)),
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
    view = request.get("view")
    if view == "result":
        row = workflow(db, revision, "revision, result")
        if row["result"] is None:
            raise ValueError("Apply preparation steps to save a result first.")
        table = json.loads(row["result"])
    elif view in ("source", "preview"):
        row = workflow(db, revision, "revision, source, custom_headers")
        columns, _, rows = source_table(row, import_details(db))
        if view == "source":
            visible = []
            total = 0
            for total, record in enumerate(rows, 1):
                if offset < total <= offset + PAGE_SIZE:
                    visible.append(record)
            return {"columns": columns, "rows": visible, "total": total, "pageSize": PAGE_SIZE}
        through = request.get("through")
        if type(through) is not int:
            raise ValueError("Select a step to preview.")
        table = execute_steps({"columns": columns, "rows": list(rows)}, request.get("steps"), through)
    else:
        raise ValueError("Choose a table to view.")
    rows = table["rows"]
    return {"columns": table["columns"], "rows": rows[offset:offset + PAGE_SIZE], "total": len(rows), "pageSize": PAGE_SIZE}


def original_record(db, request):
    line = request.get("line")
    if type(line) is not int or line < 1:
        raise ValueError("Choose a valid CSV start line.")
    row = saved_workflow(db, "name, source, custom_headers")
    if row is None:
        raise ValueError("Import a CSV into this project first.")
    details = import_details(db)
    if request.get("sourceId") != details["source_id"]:
        raise ValueError("This CSV source is unavailable in the project.")
    _, names, rows = source_table(row, details)
    for start_line, cells in rows:
        if start_line == line:
            return {"sourceId": details["source_id"], "name": row["name"], "line": line,
                    "columns": names, "cells": cells}
        if start_line > line:
            break
    raise ValueError(f"No original CSV record starts on line {line}.")


def apply(db, request):
    row = workflow(db, request.get("revision"), "revision, source, custom_headers")
    steps = request.get("steps")
    columns, _, rows = source_table(row, import_details(db))
    table = execute_steps({"columns": columns, "rows": list(rows)}, steps)
    db.execute("UPDATE csv_workflow SET steps = ?, result = ?, revision = revision + 1 WHERE singleton = 1", (
        json.dumps(steps), json.dumps(table, separators=(",", ":")),
    ))
    return state(db)
