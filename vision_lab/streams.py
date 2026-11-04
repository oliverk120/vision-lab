"""Derived streams: smaller, fixed-rate copies of the source for cheap analysis."""
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class StreamConfig:
    name: str
    width: int
    height: int
    gray: bool
    fps: Fraction


STREAM_A = StreamConfig("A", 64, 64, gray=True, fps=Fraction(15))    # cheap continuous analysis
STREAM_B = StreamConfig("B", 320, 320, gray=False, fps=Fraction(1))  # e.g. future object detection


@dataclass(frozen=True)
class Sample:
    """One derived-stream image and the source frame (index, exact time) it came from."""
    stream: str
    frame: object
    pixels: np.ndarray


class Sampler:
    """Picks frames for a fixed-rate stream using source timestamps.

    Time slots are 0, 1/fps, 2/fps, ... and each slot takes the first frame at or after it.
    A frame is never used twice; slots that pass with no frame (gaps, or a rate above the
    source's) are counted in `missed`.
    """

    def __init__(self, fps):
        self.period = 1 / Fraction(str(fps))
        self.next = Fraction(0)
        self.missed = 0

    def accept(self, time) -> bool:
        if time < self.next:
            return False
        skipped = (time - self.next) // self.period
        self.missed += skipped
        self.next += (skipped + 1) * self.period
        return True


def sample_indices(times, fps) -> list[int]:
    """Frame numbers a stream selects from a whole recording (same rule as live sampling)."""
    sampler = Sampler(fps)
    return [i for i, t in enumerate(times) if sampler.accept(t)]


def derive(frame, config: StreamConfig) -> Sample:
    """Shrink a frame to fit the stream size without distortion (black bars), then optionally grey."""
    image = Image.fromarray(frame.resized(config.width, config.height))
    canvas = Image.new("RGB", (config.width, config.height))
    canvas.paste(image, ((config.width - image.width) // 2, (config.height - image.height) // 2))
    if config.gray:
        canvas = canvas.convert("L")
    return Sample(config.name, frame, np.asarray(canvas))
