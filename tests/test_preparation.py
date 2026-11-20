"""CSV preparation through the project-bound local HTTP API."""

from base64 import b64encode
import codecs
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from functools import partial
from http.client import HTTPConnection
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from runtime import csv_source, preparation, server
from runtime.navigation import ProjectSession
from runtime.projects import ProjectStore


FIXTURES = Path(__file__).with_name("fixtures")
VALID = (FIXTURES / "csv-valid.csv").read_bytes()
INVALID = (FIXTURES / "csv-invalid-decimal.csv").read_bytes()
RENAME = {"operation": "rename", "column": 2, "name": "Prepared quantity"}
FILTER = {"operation": "filter", "column": 1, "mode": "keep", "value": "Keep"}
DECIMAL = {"operation": "convert", "column": 2, "target": "decimal", "locale": "de-DE"}
STEPS = [RENAME, FILTER, DECIMAL]


class PreparationTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.app, self.data = root / "app", root / "data"
        self.app.mkdir()
        self.data.mkdir()
        store = ProjectStore(self.app)
        folder = store.choose(self.data)["folder"]
        self.project, = store.create(folder, "Aster")["projects"]
        self.project, self.other = store.create(folder, "Birch")["projects"]
        self.http = server.LocalServer((server.HOST, 0), partial(server.AssetHandler, assets={}))
        self.http.projects = store
        self.http.navigation.active = ProjectSession(self.project["key"], folder)
        self.origin = f"http://{server.HOST}:{self.http.server_port}"
        thread = Thread(target=self.http.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.http.shutdown)

    def post(self, action, data=None, *, key=None, origin=None):
        body = {"key": key or self.project["key"], "session": self.http.navigation.active.id, **(data or {})}
        with closing(HTTPConnection(server.HOST, self.http.server_port, timeout=10)) as connection:
            connection.request("POST", "/api/" + action, json.dumps(body), {
                "Origin": self.origin if origin is None else origin, "Content-Type": "application/json",
            })
            response = connection.getresponse()
            content = response.read()
        return response.status, json.loads(content) if response.status != 403 else None

    def ok(self, action, data=None, *, key=None):
        status, response = self.post(action, data, key=key)
        self.assertEqual(status, 200, response)
        return response

    def upload(self, data, headers=None, *, key=None, origin=None, **options):
        return self.post("csv-import", {
            "name": "synthetic.csv", "content": b64encode(data).decode(), "headers": headers, **options,
        }, key=key, origin=origin)

    def preview(self, data, **options):
        return self.ok("csv-preview", {"name": "synthetic.csv", "content": b64encode(data).decode(), **options})

    def stored_workflow(self):
        with closing(sqlite3.connect(self.data / self.project["file"])) as db:
            return db.execute("SELECT source, steps, result, revision FROM csv_workflow").fetchone()

    def test_valid_flow_step_order_preview_apply_and_restart(self):
        self.assertIsNone(self.ok("preparation")["source"])
        status, initial = self.upload(VALID)
        self.assertEqual(status, 200, initial)
        self.assertEqual(initial["source"]["bytes"], len(VALID))
        source_id = initial["source"]["id"]
        source = self.ok("csv-page", {"view": "source", "revision": 1})
        self.assertEqual(source["rows"][0], [2, ["0007", "Keep", "12,50", 'Synthetic; "quoted"']])
        self.assertEqual(source["rows"][2], [4, ["0042", "Keep", "-0,075", "Two\nfixture lines"]])
        self.assertEqual(source["columns"][2], {"name": "Quantity", "type": "text"})

        preview_request = {"view": "preview", "revision": 1, "steps": STEPS}
        first = self.ok("csv-page", {**preview_request, "through": 0})
        self.assertEqual(first["total"], 3)
        self.assertEqual(first["columns"][2], {"name": "Prepared quantity", "type": "text"})
        with_filter = self.ok("csv-page", {**preview_request, "through": 1})
        self.assertEqual(with_filter["total"], 2)
        self.assertEqual(with_filter["rows"][0][1][2], "12,50")
        status, error = self.post("csv-page", {**preview_request, "steps": [RENAME, DECIMAL, FILTER], "through": 2})
        self.assertEqual(status, 400)
        self.assertIn("CSV line 3, column 3 (Quantity)", error["error"])

        preview = self.ok("csv-page", {**preview_request, "through": 2})
        self.assertEqual(preview["columns"][2], {"name": "Prepared quantity", "type": "decimal"})
        self.assertEqual(preview["rows"], [
            [2, ["0007", "Keep", "12.50", 'Synthetic; "quoted"']],
            [4, ["0042", "Keep", "-0.075", "Two\nfixture lines"]],
        ])
        applied = self.ok("csv-apply", {"steps": STEPS, "revision": 1})["source"]
        self.assertTrue(applied["hasResult"])
        self.assertEqual(preview, self.ok("csv-page", {"view": "result", "revision": 2}))
        original_bytes, saved_steps, result, _ = self.stored_workflow()
        self.assertEqual(original_bytes, VALID)
        self.assertEqual(json.loads(saved_steps), STEPS)
        self.assertEqual(self.post("preparation", key=self.other["key"])[0], 400)
        with self.http.projects.open_database(self.other["key"]) as (db, _, _):
            self.assertIsNone(preparation.state(db)["source"])

        restarted = ProjectStore(self.app)
        self.http.projects = restarted
        folder = restarted.choose(self.data)
        reopened = folder["projects"][0]["key"]
        self.http.navigation.active = ProjectSession(reopened, folder["folder"])
        self.assertNotEqual(reopened, self.project["key"])
        self.assertEqual(self.ok("preparation", key=reopened)["source"], applied)
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 2}, key=reopened), preview)
        record = self.ok("csv-record", {"sourceId": source_id, "line": 4}, key=reopened)
        self.assertEqual(record["name"], "synthetic.csv")
        self.assertEqual(record["cells"], ["0042", "Keep", "-0,075", "Two\nfixture lines"])
        self.assertEqual(self.post("csv-record", {"sourceId": source_id, "line": 5}, key=reopened)[0], 400)
        self.assertEqual(self.post("csv-record", {"sourceId": source_id, "line": 4}, key="unknown")[0], 400)
        self.ok("csv-apply", {"steps": applied["steps"], "revision": 2}, key=reopened)
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 3}, key=reopened), preview)
        self.assertEqual(self.stored_workflow()[:3], (original_bytes, saved_steps, result))

    def test_invalid_decimal_keeps_previous_steps_result_and_bytes(self):
        self.assertEqual(self.upload(INVALID)[0], 200)
        as_text = {**DECIMAL, "target": "text"}
        self.ok("csv-apply", {"steps": [RENAME, as_text], "revision": 1})
        original = self.stored_workflow()
        self.assertEqual(original[0], INVALID)
        invalid = {"steps": [RENAME, DECIMAL], "revision": 2}
        failed_preview = self.post("csv-page", {**invalid, "view": "preview", "through": 1})
        failed_apply = self.post("csv-apply", invalid)
        self.assertEqual(failed_preview, failed_apply)
        self.assertEqual(failed_apply, (400, {"error": "Step 2: invalid decimal at CSV line 4, column 3 (Quantity)."}))
        self.assertEqual(self.stored_workflow(), original)
        saved = self.ok("csv-page", {"view": "result", "revision": 2})
        self.assertEqual(saved["rows"][1], [4, ["0008", "Keep", "not-a-number", "Invalid synthetic quantity"]])
        self.assertEqual(self.upload(VALID)[0], 400)
        self.assertEqual(self.stored_workflow(), original)

    def test_custom_headers_utf8_bom_exact_values_and_locale(self):
        data = b'\xef\xbb\xbf0007;1.00000000000000000000000009;"a\r\nb"\r\n'
        self.assertEqual(self.upload(data, 'Code;Value;"Quoted; header"')[0], 200)
        state = self.ok("preparation")["source"]
        self.assertEqual([column["name"] for column in state["columns"]], ["Code", "Value", "Quoted; header"])
        steps = [{**DECIMAL, "column": 1, "locale": "en-US"}]
        self.ok("csv-apply", {"steps": steps, "revision": 1})
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 2})["rows"], [
            [1, ["0007", "1.00000000000000000000000009", "a\r\nb"]],
        ])
        self.assertEqual(self.stored_workflow()[0], data)

    def test_preview_detects_supported_encodings_and_quoted_delimiters(self):
        comma = 'Article, Note \r\n0007,"Ä;ß\r\n€"\r\n0042,Text\r\n'
        semicolon = 'Article; Note \r\n0007;"Ä,ß\r\n€"\r\n0042;Text\r\n'
        cases = [
            ("utf-8", comma.encode(), ",", "Ä;ß\r\n€"),
            ("utf-8", codecs.BOM_UTF8 + comma.encode(), ",", "Ä;ß\r\n€"),
            ("utf-16-le", codecs.BOM_UTF16_LE + comma.encode("utf-16-le"), ",", "Ä;ß\r\n€"),
            ("utf-16-le", semicolon.encode("utf-16-le"), ";", "Ä,ß\r\n€"),
            ("utf-16-be", codecs.BOM_UTF16_BE + comma.encode("utf-16-be"), ",", "Ä;ß\r\n€"),
            ("utf-16-be", semicolon.encode("utf-16-be"), ";", "Ä,ß\r\n€"),
            ("windows-1252", semicolon.encode("cp1252"), ";", "Ä,ß\r\n€"),
        ]
        for encoding, data, delimiter, expected in cases:
            with self.subTest(encoding=encoding, delimiter=delimiter):
                response = self.preview(data)
                self.assertIsNone(response["error"])
                self.assertEqual(response["suggestedEncoding"], encoding)
                self.assertEqual(response["suggestedDelimiter"], delimiter)
                self.assertEqual(response["sample"]["rows"], [[2, ["0007", expected]], [4, ["0042", "Text"]]])
        self.assertIsNone(self.ok("preparation")["source"])

    def test_explicit_import_options_persist_with_headerless_data_and_raw_bytes(self):
        data = b"0007;\xc3\xa4,1\r\n0042;Text,2\r\n"
        ambiguous = self.preview(data)
        self.assertEqual(ambiguous["suggestedEncoding"], "utf-8")
        self.assertIsNone(ambiguous["suggestedDelimiter"])
        self.assertIsNone(ambiguous["sample"])
        self.assertIn("Choose a delimiter", ambiguous["error"])
        options = {"encoding": "windows-1252", "delimiter": ",", "headers": "Code,Quantity"}
        corrected = self.preview(data, **options)
        first = data.decode("cp1252").split(",")[0]
        self.assertEqual(corrected["sample"]["rows"][0], [1, [first, "1"]])
        self.assertIsNone(self.ok("preparation")["source"])

        status, saved = self.upload(data, **options)
        self.assertEqual(status, 200, saved)
        self.assertEqual(self.stored_workflow()[0], data)
        source = saved["source"]
        self.assertEqual(source["importOptions"], {"encoding": "windows-1252", "delimiter": ",", "hasHeader": False})
        self.assertEqual(source["columnMetadata"][0], {"position": 1, "originalName": "Code", "assigned": True,
                                                        "samples": [first, "0042;Text"]})
        self.assertEqual(self.ok("csv-page", {"view": "source", "revision": 1})["rows"], corrected["sample"]["rows"])

    def test_preview_ignores_incomplete_tail_and_import_rejects_late_errors(self):
        prefix = b"Article;Note\r\n" + b"0007;SAMPLE\r\n" * 12
        cut = self.preview(prefix + b'0042;"open\r\ncut', truncated=True)
        self.assertEqual(len(cut["sample"]["rows"]), 10)
        for tail, error in ((b'0042;"unfinished\r\nrecord', "Invalid CSV at line 14"),
                            (b"0042;extra;column\r\n", "CSV line 14 has 3 fields"),
                            (b"0042;\xff\r\n", "Cannot read this CSV as UTF-8")):
            with self.subTest(error=error):
                data = prefix + tail
                preview = self.preview(data, encoding="utf-8")
                self.assertEqual(len(preview["sample"]["rows"]), 10)
                self.assertIsNone(self.ok("preparation")["source"])
                status, response = self.upload(data, encoding="utf-8", delimiter=";")
                self.assertEqual(status, 400)
                self.assertIn(error, response["error"])
                self.assertIsNone(self.ok("preparation")["source"])

        cut = self.preview(b'Article;Note\r\n0007;complete\r\n0042;"partial\r\nnext', truncated=True)
        self.assertEqual(cut["sample"]["rows"], [[2, ["0007", "complete"]]])

    def test_v011_workflow_reopens_with_metadata_and_original_record(self):
        columns = [{"name": name, "type": "text"} for name in ("Article", "Kind", "Quantity", "Note")]
        old_result = {"columns": columns, "rows": [[2, ["0007", "Keep", "12,50", 'Synthetic; "quoted"']],
                                                  [4, ["0042", "Keep", "-0,075", "Two\nfixture lines"]]]}
        with closing(sqlite3.connect(self.data / self.project["file"])) as db, db:
            db.execute("""CREATE TABLE csv_workflow (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1), name TEXT NOT NULL,
                source BLOB NOT NULL, custom_headers TEXT NOT NULL, columns TEXT NOT NULL,
                steps TEXT NOT NULL, result TEXT, revision INTEGER NOT NULL
            )""")
            db.execute("INSERT INTO csv_workflow VALUES (1, ?, ?, 'null', ?, ?, ?, 2)",
                       ("legacy.csv", VALID, json.dumps(columns), json.dumps([FILTER]), json.dumps(old_result)))
        initial = self.ok("preparation")["source"]
        self.assertEqual(initial["importOptions"], {"encoding": "utf-8", "delimiter": ";", "hasHeader": True})
        self.assertFalse(initial["columnMetadata"][0]["assigned"])
        self.assertEqual(initial["steps"], [FILTER])
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 2})["rows"], old_result["rows"])
        record = self.ok("csv-record", {"sourceId": initial["id"], "line": 4})
        self.assertEqual(record["cells"], old_result["rows"][1][1])
        reapplied = self.ok("csv-apply", {"steps": [FILTER], "revision": 2})["source"]
        self.assertEqual(reapplied["id"], initial["id"])
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 3})["rows"], old_result["rows"])

    def test_invalid_import_has_no_side_effect_and_protects_project_reference(self):
        for data, header, error in [
            (b"Label;Value\nrow;\xff", None, "UTF-8"),
            (b"Label;Label\n1;2", None, "unique"),
            (b"x;y", "Only one name", "CSV line 1 has 2 fields"),
            (b'Label;Value\nrow;"oops', None, "Invalid CSV at line 2"),
        ]:
            with self.subTest(error=error):
                status, response = self.upload(data, header)
                self.assertEqual(status, 400)
                self.assertIn(error, response["error"])
                self.assertIsNone(self.ok("preparation")["source"])
        self.assertEqual(self.upload(VALID, origin="null")[0], 403)
        self.assertEqual(self.upload(VALID, key="unknown")[0], 400)
        self.assertIsNone(self.ok("preparation")["source"])

    def test_multiline_filters_match_browser_newlines_without_rewriting_values(self):
        data = b'Article;Note\r\n0007;"Alpha\r\nBeta"\r\n0011;"Alpha\nBeta"\r\n0015;"Alpha\rBeta"\r\n0020;"Alpha\r\nBeta "\r\n'
        self.assertEqual(self.upload(data)[0], 200)
        steps = [{**FILTER, "value": "Alpha\nBeta"}]
        preview_request = {"view": "preview", "through": 0, "revision": 1, "steps": steps}
        rows = self.ok("csv-page", preview_request)["rows"]
        self.assertEqual([row[1] for row in rows], [
            ["0007", "Alpha\r\nBeta"], ["0011", "Alpha\nBeta"], ["0015", "Alpha\rBeta"],
        ])
        self.ok("csv-apply", {"steps": steps, "revision": 1})
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 2})["rows"], rows)

        steps = [{**steps[0], "mode": "remove"}]
        remaining = self.ok("csv-page", {**preview_request, "revision": 2, "steps": steps})["rows"]
        self.assertEqual(remaining, [[8, ["0020", "Alpha\r\nBeta "]]])
        self.ok("csv-apply", {"steps": steps, "revision": 2})
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 3})["rows"], remaining)
        self.assertEqual(self.stored_workflow()[0], data)

    def test_simultaneous_applies_cannot_overwrite_newer_revision(self):
        self.assertEqual(self.upload(VALID)[0], 200)

        def apply(name):
            return self.post("csv-apply", {"steps": [{**RENAME, "name": name}], "revision": 1})

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(apply, ["First", "Second"])
        self.assertCountEqual([first[0], second[0]], [200, 400])
        success, failure = (first, second) if first[0] == 200 else (second, first)
        self.assertIn("Another window saved", failure[1]["error"])
        self.assertEqual(self.ok("preparation")["source"], success[1]["source"])

    def test_generated_csv_at_one_mib_and_page_through_last_row(self):
        header = b"Article;Kind;Quantity;Note\n"
        line = b"0007;Keep;12,50;" + b"x" * 55 + b"\n"
        last = b"0042;Keep;1,25;end"
        count, padding = divmod(1_048_576 - len(header) - len(last), len(line))
        data = header + line * count + last + b"x" * padding
        self.assertEqual(len(data), 1_048_576)
        self.assertEqual(self.upload(data)[0], 200)
        self.ok("csv-apply", {"steps": STEPS, "revision": 1})
        page_size = preparation.PAGE_SIZE
        page = self.ok("csv-page", {"view": "result", "revision": 2, "offset": count // page_size * page_size})
        self.assertEqual(page["total"], count + 1)
        self.assertLessEqual(len(page["rows"]), page_size)
        self.assertEqual(page["rows"][-1], [count + 2, ["0042", "Keep", "1.25", "end" + "x" * padding]])
        self.assertEqual(self.stored_workflow()[0], data)

    def test_generated_daily_import_preview_and_last_record(self):
        header = "Order;Article;Quantity;Description;Zone\r\n"
        body = (f"{row:08d};{row % 17:04d};{row % 100},50;Äußere Lagerzone – Referenz €;West\r\n"
                for row in range(1, 150_000))
        last = '00150000;0042;12,50;"Mehrere\r\nZeilen";West\r\n'
        payload = (header + "".join(body) + last).encode("cp1252")
        self.assertGreater(len(payload), 1_048_576)
        sample = self.preview(payload[:csv_source.MAX_PREVIEW_BYTES], truncated=True)
        self.assertEqual(sample["suggestedEncoding"], "windows-1252")
        self.assertEqual(len(sample["sample"]["rows"]), 10)
        self.assertIsNone(self.ok("preparation")["source"])
        status, saved = self.upload(payload, encoding="windows-1252", delimiter=";")
        self.assertEqual(status, 200, saved)
        self.assertEqual(self.stored_workflow()[0], payload)
        last_page = self.ok("csv-page", {"view": "source", "revision": 1, "offset": 149_999})
        self.assertEqual(last_page["total"], 150_000)
        self.assertEqual(last_page["rows"], [[150_001, ["00150000", "0042", "12,50", "Mehrere\r\nZeilen", "West"]]])
        steps = [{**FILTER, "value": "0042"}, DECIMAL]
        applied = self.ok("csv-apply", {"steps": steps, "revision": 1})["source"]
        result = self.ok("csv-page", {"view": "result", "revision": 2})
        self.assertEqual(result["rows"], [[150_001, ["00150000", "0042", "12.50", "Mehrere\r\nZeilen", "West"]]])
        record = self.ok("csv-record", {"sourceId": applied["id"], "line": 150_001})
        self.assertEqual(record["cells"], last_page["rows"][0][1])
