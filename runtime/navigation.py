"""Coordinate a single project and its Edge app instance."""

from contextlib import contextmanager
from threading import Condition, Thread
from urllib.parse import urlencode
from uuid import uuid4


class ProjectSession:
    def __init__(self, key, folder):
        self.key = key
        self.folder = folder
        self.id = uuid4().hex
        self.ready = False
        self.handoff = False
        self.ended = False
        self.writes = 0
        self.closing = False


class Navigation:
    def __init__(self, launch):
        self.launch = launch
        self.changed = Condition()
        self.active = None

    def open(self, key, folder, origin):
        with self.changed:
            if self.active is not None:
                raise ValueError("Close the active project before opening another.")
            session = ProjectSession(key, folder)
            query = urlencode({"project": key, "session": session.id})
            process = self.launch(f"{origin}/project#{query}")
            self.active = session
            Thread(target=self.wait_for_close, args=(process, session, origin), daemon=True).start()
            self.changed.wait_for(lambda: session.ready or session.ended, timeout=15)
            if session.ready and not session.ended:
                session.handoff = True
                return
            # Ignore late readiness after a failed start. This process has a private profile.
            session.ended = True
            if process.poll() is None:
                process.terminate()
            raise RuntimeError("The project window did not become ready. Try opening it again.")

    def wait_for_close(self, process, session, origin):
        process.wait()
        with self.changed:
            session.ended = True
            self.changed.notify_all()
            self.changed.wait_for(lambda: session.writes == 0)
            self.active = None
            if session.handoff:
                try:
                    query = urlencode({"folder": session.folder})
                    self.launch(f"{origin}/launcher?{query}")
                except RuntimeError as error:
                    print(f"Warehouse Studio: {error}", flush=True)

    def _session(self, session_id, key):
        session = self.active
        if session is None or session.ended or (session.id, session.key) != (session_id, key):
            raise ValueError("This project window does not belong to the active project.")
        return session

    def ready(self, session_id, key):
        with self.changed:
            session = self._session(session_id, key)
            session.ready = True
            self.changed.notify_all()

    def close(self, session_id, key):
        with self.changed:
            session = self._session(session_id, key)
            if session.writes:
                raise ValueError("A write is still running. Wait for it to finish, then close the project.")
            session.closing = True

    @contextmanager
    def use(self, session_id, key, write=False):
        with self.changed:
            session = self._session(session_id, key)
            if session.closing:
                raise ValueError("The project is closing.")
            if write:
                session.writes += 1
        try:
            yield
        finally:
            if write:
                with self.changed:
                    session.writes -= 1
                    self.changed.notify_all()
