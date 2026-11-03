"""Read-only source decoding. Pixels are decoded on demand, never indexed in RAM."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Protocol, Iterator

import av
import numpy as np


def time_value(value) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(str(value))


@dataclass(frozen=True)
class Frame:
    sequence: int
    pts: int
    time_base: Fraction
    timestamp: Fraction
    pixels: np.ndarray
    source_id: str = ""
    epoch: int = 0


class VideoSource(Protocol):
    def frames(self, start=0, epoch=0) -> Iterator[Frame]: ...
    def get(self, sequence: int, epoch=0) -> Frame: ...


class FileSource:
    """Build a compact PTS index; decode each requested range with bounded pixels.

    Seeking currently decodes from the beginning to preserve exact sequence IDs,
    including duplicate PTS. This favors correctness over random-access latency.
    """
    capabilities = {"seek": True, "finite": True, "speed": True}

    def __init__(self, path, source_id=""):
        self.path = Path(path)
        self.source_id = source_id or self.path.stem
        self.index = []
        with av.open(str(self.path)) as container:
            if not container.streams.video:
                raise ValueError("File has no video stream")
            stream = container.streams.video[0]
            self.metadata = dict(codec=stream.codec_context.name,
                                 width=stream.width, height=stream.height,
                                 fps=float(stream.average_rate) if stream.average_rate else None,
                                 size_bytes=self.path.stat().st_size)
            self.origin = None
            previous = None
            last_duration = Fraction(0)
            for f in container.decode(stream):
                if f.pts is None or f.time_base is None:
                    raise ValueError("Missing presentation timestamps are unsupported")
                absolute = f.pts * f.time_base
                if self.origin is None:
                    self.origin = absolute
                t = absolute - self.origin
                if previous is not None and t < previous:
                    raise ValueError("Nonmonotonic presentation timestamps are unsupported")
                self.index.append((f.pts, Fraction(f.time_base), t))
                last_duration = (f.duration or 0) * f.time_base
                previous = t
            if not self.index:
                raise ValueError("Video contains no decoded frames")
            if last_duration <= 0:
                last_duration = (self.index[-1][2] - self.index[-2][2]
                                 if len(self.index) > 1 else Fraction(1, 30))
            self.duration = self.index[-1][2] + max(last_duration, Fraction(1, 1000000))
            self.metadata.update(duration=float(self.duration), frames=len(self.index),
                                 time_base=str(self.index[0][1]),
                                 first_pts=self.index[0][0],
                                 vfr=len({self.index[i][2]-self.index[i-1][2]
                                          for i in range(1, len(self.index))}) > 1)

    def frames(self, start=0, epoch=0):
        start = time_value(start)
        with av.open(str(self.path)) as container:
            for sequence, raw in enumerate(container.decode(video=0)):
                pts, base, t = self.index[sequence]
                if t < start:
                    continue
                pixels = raw.to_ndarray(format="rgb24")
                # Display-matrix rotation is exposed by modern PyAV VideoFrame.
                rotation = int(round(getattr(raw, "rotation", 0))) % 360
                if rotation in (90, 180, 270):
                    pixels = np.rot90(pixels, k=rotation // 90).copy()
                elif rotation:
                    raise ValueError("Only right-angle phone orientation is supported")
                pixels.setflags(write=False)
                yield Frame(sequence, pts, base, t, pixels, self.source_id, epoch)

    def get(self, sequence, epoch=0):
        if not 0 <= sequence < len(self.index):
            raise IndexError(sequence)
        generator = self.frames(self.index[sequence][2], epoch)
        try:
            for frame in generator:
                if frame.sequence == sequence:
                    return frame
        finally:
            generator.close()
        raise IndexError(sequence)
