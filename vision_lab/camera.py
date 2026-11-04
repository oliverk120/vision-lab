"""Simulated camera: replays a video as if it were arriving live.

    video source ─▶ rolling cache (high resolution) ─▶ derived streams A, B ─▶ future analysis

Frames "arrive" when simulated time reaches their timestamp. Each arrival enters the cache and
is offered to every stream. Future analysis (motion detection, neural networks) should consume the
Samples returned by update(), and fetch high-resolution detail from `cache`.
"""
import time

from .cache import RollingCache
from .streams import STREAM_A, STREAM_B, Sampler, derive


class SimulatedCamera:
    def __init__(self, source, streams=(STREAM_A, STREAM_B), cache_seconds=600, clock=time.monotonic):
        self.source, self.streams, self.clock = source, list(streams), clock
        self.cache = RollingCache(source, cache_seconds)
        self.speed = 1.0
        self._frames = None
        self.restart()

    def restart(self):
        """Back to the start: empty cache, fresh streams, paused."""
        if self._frames:
            self._frames.close()
        self._frames = self.source.frames()
        self._next = next(self._frames, None)
        self.cache.clear()
        self.samplers = {s.name: Sampler(s.fps) for s in self.streams}
        self.latest = {}       # stream name -> most recent Sample
        self.frame = None      # most recent source frame
        self.arrived = 0
        self.finished = False
        self.playing = False
        self.update_seconds = 0.0  # processing time of the last update()
        self._elapsed, self._anchor = 0.0, None

    @property
    def time(self) -> float:
        """Simulated seconds since the recording started."""
        if self.playing:
            return self._elapsed + (self.clock() - self._anchor) * self.speed
        return self._elapsed

    def play(self):
        if not self.playing and not self.finished:
            self._anchor, self.playing = self.clock(), True

    def pause(self):
        self._elapsed, self.playing = self.time, False

    def set_speed(self, speed: float):
        if speed <= 0:
            raise ValueError("Speed must be positive")
        self._elapsed, self._anchor, self.speed = self.time, self.clock(), speed

    def update(self, limit: int = 60) -> list:
        """Deliver every frame whose time has come (at most `limit`); return the new derived Samples."""
        if not self.playing:
            return []
        started = time.perf_counter()
        now, samples = self.time, []
        for _ in range(limit):
            frame = self._next
            if frame is None:
                self.finished = True
                self.pause()
                break
            if frame.time > now:
                break
            self._next = next(self._frames, None)
            self.frame = frame
            self.cache.add(frame)
            self.arrived += 1
            for config in self.streams:
                if self.samplers[config.name].accept(frame.time):
                    self.latest[config.name] = derive(frame, config)
                    samples.append(self.latest[config.name])
        self.update_seconds = time.perf_counter() - started
        return samples
