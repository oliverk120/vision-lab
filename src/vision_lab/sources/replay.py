"""Cooperative replay: bounded ticks, injectable clock, explicit epochs."""
import math
import time
from vision_lab.cache import RollingCache
from vision_lab.sources import time_value
from vision_lab.streams import Sampler


class Replay:
    def __init__(self, source, streams, retention=600, clock=time.monotonic):
        self.source, self.streams, self.clock = source, streams, clock
        self.cache = RollingCache(source, retention)
        self.epoch = -1
        self.speed = 1.0
        self.mode = "paced"
        self.loop = False
        self._iterator = None
        self.seek(0)

    @property
    def position(self):
        if self.playing and self.mode == "paced":
            return min(float(self.source.duration), self._position + (self.clock()-self._wall)*self.speed)
        return self._position

    def play(self):
        if self.playing:
            return
        self._wall = self.clock()
        self.playing = not self.eof

    def pause(self):
        self._position = self.position
        self.playing = False

    def set_speed(self, speed):
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("Speed must be finite and positive")
        self._position = self.position
        self._wall = self.clock()
        self.speed = speed

    def set_mode(self, mode):
        if mode not in ("paced", "offline"):
            raise ValueError("Unknown replay mode")
        self.pause()
        self.mode = mode

    def seek(self, target):
        target = time_value(target)
        if target < 0 or target > self.source.duration:
            raise ValueError("Seek outside recording")
        if self._iterator is not None:
            self._iterator.close()
        self.epoch += 1
        self.cache.reset(self.epoch)
        self.samplers = {name: Sampler(config, target) for name, config in self.streams.items()}
        self.latest = {}
        self.frame = None
        self._position = float(target)
        self._wall = self.clock()
        self.playing = False
        self.eof = False
        self.count = 0
        self.processing_seconds = 0.0
        self._iterator = self.source.frames(target, self.epoch)
        self._pending = None

    def restart(self):
        self.seek(0)

    def tick(self, limit=32):
        if not self.playing:
            return 0
        started = time.perf_counter()
        count = 0
        for _ in range(limit):
            if self._pending is None:
                self._pending = next(self._iterator, None)
            if self._pending is None:
                self.pause()
                self.eof = True
                if self.loop:
                    self.restart()
                    self.play()
                break
            if self.mode == "paced" and float(self._pending.timestamp) > self.position + 1e-9:
                break
            self.frame = self._pending
            self._pending = None
            self.cache.ingest(self.frame)
            if self.mode == "offline":
                self._position = float(self.frame.timestamp)
            for name, sampler in self.samplers.items():
                sample = sampler.consume(self.frame)
                if sample is not None:
                    self.latest[name] = sample
            count += 1
            self.count += 1
        self.processing_seconds += time.perf_counter()-started
        return count

    def close(self):
        self.pause()
        self._iterator.close()
