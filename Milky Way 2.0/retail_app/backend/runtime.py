"""Cooperative cancellation shared by the job runner and optional agent tools."""
import threading
import time


class JobCancelled(Exception):
    """Raised at an execution boundary after a local user requests Stop."""


class JobControl:
    def __init__(self, notify, timeout=300):
        self._notify = notify
        self._cancelled = threading.Event()
        self.deadline = time.monotonic() + timeout

    def cancel(self):
        self._cancelled.set()

    def check_cancelled(self):
        if time.monotonic() >= self.deadline:
            raise ValueError('The analysis reached its five-minute time limit. Narrow the question and retry.')
        if self._cancelled.is_set():
            raise JobCancelled('Answer stopped. You can retry your question.')

    def wait(self, seconds):
        self._cancelled.wait(min(seconds, max(0, self.deadline-time.monotonic())))
        self.check_cancelled()

    def __call__(self, message):
        self.check_cancelled()
        self._notify(message)
