"""CSV preparation through the project-bound local HTTP API."""

from base64 import b64encode
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

from runtime import preparation, server
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
        self.origin = f"http://{server.HOST}:{self.http.server_port}"
        thread = Thread(target=self.http.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.http.shutdown)

    def post(self, action, data=None, *, key=None, origin=None):
        body = {"key": key or self.project["key"], **(data or {})}
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

    def upload(self, data, headers=None, *, key=None, origin=None):
        return self.post("csv-import", {"name": "synthetic.csv", "content": b64encode(data).decode(), "headers": headers},
                         key=key, origin=origin)

    def stored_workflow(self):
        with closing(sqlite3.connect(self.data / self.project["file"])) as db:
            return db.execute("SELECT source, steps, result, revision FROM csv_workflow").fetchone()

    def test_valid_flow_step_order_preview_apply_and_restart(self):
        self.assertIsNone(self.ok("preparation")["source"])
        status, initial = self.upload(VALID)
        self.assertEqual(status, 200, initial)
        self.assertEqual(initial["source"]["bytes"], len(VALID))
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
        self.assertIsNone(self.ok("preparation", key=self.other["key"])["source"])

        restarted = ProjectStore(self.app)
        self.http.projects = restarted
        reopened = restarted.choose(self.data)["projects"][0]["key"]
        self.assertNotEqual(reopened, self.project["key"])
        self.assertEqual(self.ok("preparation", key=reopened)["source"], applied)
        self.assertEqual(self.ok("csv-page", {"view": "result", "revision": 2}, key=reopened), preview)
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
        count, padding = divmod(preparation.MAX_SOURCE_BYTES - len(header) - len(last), len(line))
        data = header + line * count + last + b"x" * padding
        self.assertEqual(len(data), 1_048_576)
        self.assertEqual(self.upload(data + b"x")[0], 400)
        self.assertEqual(self.upload(data)[0], 200)
        self.ok("csv-apply", {"steps": STEPS, "revision": 1})
        page_size = preparation.PAGE_SIZE
        page = self.ok("csv-page", {"view": "result", "revision": 2, "offset": count // page_size * page_size})
        self.assertEqual(page["total"], count + 1)
        self.assertLessEqual(len(page["rows"]), page_size)
        self.assertEqual(page["rows"][-1], [count + 2, ["0042", "Keep", "1.25", "end" + "x" * padding]])
        self.assertEqual(self.stored_workflow()[0], data)
