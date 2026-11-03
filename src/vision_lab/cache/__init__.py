"""Logical retention over arrived frames; source handles never reach plugins."""
from collections import deque
from vision_lab.sources import time_value


class CacheError(ValueError):
    pass


class RollingCache:
    def __init__(self, source, retention=600):
        self._source = source
        self.retention = time_value(retention)
        if self.retention <= 0:
            raise ValueError("Retention must be positive")
        self.reset(0)

    def reset(self, epoch):
        self.epoch = epoch
        self.arrived = deque()
        self.watermark = None
        self.first = None

    def ingest(self, frame):
        if frame.epoch != self.epoch:
            raise CacheError("STALE_EPOCH")
        if self.watermark is not None and frame.timestamp < self.watermark:
            raise CacheError("INVALID_REQUEST: unordered arrival")
        self.watermark = frame.timestamp
        if self.first is None:
            self.first = frame.timestamp
        self.arrived.append((frame.timestamp, frame.sequence))
        while self.arrived and self.arrived[0][0] < self.watermark-self.retention:
            self.arrived.popleft()

    def availability(self):
        return dict(epoch=self.epoch, start=None if self.first is None else float(max(self.first, self.watermark-self.retention)),
                    end=None if self.watermark is None else float(self.watermark),
                    frames=len(self.arrived))

    def _check(self, timestamp, epoch=None):
        t = time_value(timestamp)
        if epoch is not None and epoch != self.epoch:
            raise CacheError("STALE_EPOCH")
        if self.watermark is None or t > self.watermark:
            raise CacheError("NOT_YET_AVAILABLE")
        if t < self.first:
            raise CacheError("OUTSIDE_EPOCH")
        if t < self.watermark-self.retention:
            raise CacheError("EXPIRED")
        return t

    def frame_at(self, timestamp, epoch=None):
        t = self._check(timestamp, epoch)
        active_epoch = self.epoch
        match = next(((ts, seq) for ts, seq in reversed(self.arrived) if ts <= t), None)
        if match is None:
            raise CacheError("NO_FRAME")
        result = self._source.get(match[1], active_epoch)
        self._check(match[0], active_epoch)
        return result

    def frames_between(self, start, end, epoch=None):
        start, end = self._check(start, epoch), self._check(end, epoch)
        if start > end:
            raise CacheError("INVALID_REQUEST")
        active_epoch = self.epoch
        wanted = {seq: ts for ts, seq in self.arrived if start <= ts <= end}
        for frame in self._source.frames(start, active_epoch):
            if frame.timestamp > end:
                break
            if frame.sequence in wanted:
                self._check(frame.timestamp, active_epoch)
                yield frame

    def crop_at(self, timestamp, box):
        frame = self.frame_at(timestamp)
        x1,y1,x2,y2 = box
        h,w = frame.pixels.shape[:2]
        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
            raise CacheError("INVALID_REQUEST")
        return frame, frame.pixels[y1:y2, x1:x2]
