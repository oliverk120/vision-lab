"""Rolling cache: the recent high-resolution footage a camera has delivered so far."""
from collections import deque
from fractions import Fraction


class NotAvailable(LookupError):
    """The requested time has not arrived yet, or has already left the cache."""


class RollingCache:
    """Remembers the last `seconds` of footage that has *arrived* from the camera.

    Requests for footage the camera has not delivered yet, or that has expired, raise NotAvailable,
    so later analysis can never peek into the future. For a video file only (time, frame number)
    pairs are kept and pixels are re-read from the unchanged original on request: almost no memory
    and no disk writes. A live camera would keep its recent frames behind the same methods.
    """

    def __init__(self, source, seconds=600):
        self.source = source
        self.seconds = Fraction(str(seconds))
        self.clear()

    def clear(self):
        self._arrived = deque()  # (time, frame index), oldest first

    def add(self, frame):
        self._arrived.append((frame.time, frame.index))
        while self._arrived[0][0] < frame.time - self.seconds:
            self._arrived.popleft()

    @property
    def span(self):
        """(oldest, newest) cached time in seconds, or None when empty."""
        return (self._arrived[0][0], self._arrived[-1][0]) if self._arrived else None

    def __len__(self):
        return len(self._arrived)

    def get(self, time):
        """The full-resolution frame showing at `time`: the latest arrived frame at or before it."""
        if not self._arrived:
            raise NotAvailable("No footage has arrived yet")
        oldest, newest = self.span
        if time > newest:
            raise NotAvailable(f"{float(time):.3f} s has not arrived yet (newest is {float(newest):.3f} s)")
        if time < oldest:
            raise NotAvailable(f"{float(time):.3f} s is no longer cached (oldest is {float(oldest):.3f} s)")
        index = next(i for t, i in reversed(self._arrived) if t <= time)
        return self.source.frame(index)
