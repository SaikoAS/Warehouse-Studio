"""Exercise the runtime's project-to-launcher handoff without starting Edge."""

from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Event
from urllib.parse import parse_qs, urlsplit
import unittest

from runtime.navigation import Navigation


class BrowserProcess:
    def __init__(self):
        self.exited = Event()

    def wait(self):
        self.exited.wait(timeout=5)


class NavigationTests(unittest.TestCase):
    def test_one_ready_project_and_one_return_after_writes_finish(self):
        launched = Queue()
        process = BrowserProcess()

        def launch(url):
            launched.put(url)
            return process

        navigation = Navigation(launch)
        origin = "http://127.0.0.1:8765"
        with ThreadPoolExecutor(max_workers=1) as pool:
            opening = pool.submit(navigation.open, "first", "folder", origin)
            address = urlsplit(launched.get(timeout=2))
            session_id = parse_qs(address.fragment)["session"][0]
            self.assertEqual(address.path, "/project")
            self.assertFalse(opening.done())
            with self.assertRaisesRegex(ValueError, "Close the active project"):
                navigation.open("second", "folder", origin)
            navigation.ready(session_id, "first")
            opening.result(timeout=2)

        with navigation.use(session_id, "first", write=True):
            with self.assertRaisesRegex(ValueError, "still running"):
                navigation.close(session_id, "first")
            process.exited.set()
            with self.assertRaises(Empty):
                launched.get(timeout=0.1)

        self.assertEqual(launched.get(timeout=2), origin + "/launcher?folder=folder")
        self.assertIsNone(navigation.active)
        self.assertTrue(launched.empty())
        with self.assertRaisesRegex(ValueError, "does not belong"):
            navigation.ready(session_id, "first")
