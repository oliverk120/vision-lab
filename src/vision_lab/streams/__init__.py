"""Causal rational sampling and observable image transforms."""
from dataclasses import dataclass
from fractions import Fraction
import math
import cv2
import numpy as np
from vision_lab.sources import Frame, time_value


@dataclass(frozen=True)
class StreamConfig:
    width: int = 64
    height: int = 64
    color: str = "gray"
    fps: float = 15.0

    def __post_init__(self):
        if not (isinstance(self.width, int) and isinstance(self.height, int)
                and 1 <= self.width <= 4096 and 1 <= self.height <= 4096):
            raise ValueError("Dimensions must be integers in 1..4096")
        if self.color not in ("gray", "rgb") or not math.isfinite(self.fps) or self.fps <= 0:
            raise ValueError("Use gray/rgb and a finite positive FPS")


@dataclass(frozen=True)
class Sample:
    frame: Frame
    target: Fraction
    pixels: np.ndarray
    transform: dict


class Sampler:
    def __init__(self, config: StreamConfig, anchor=0):
        self.config = config
        self.period = 1 / time_value(config.fps)
        self.next = time_value(anchor)
        self.missed = 0
        self.last = None

    def accept(self, timestamp):
        timestamp = time_value(timestamp)
        if self.last is not None and timestamp < self.last:
            raise ValueError("Sampler requires ordered timestamps")
        self.last = timestamp
        if timestamp < self.next:
            return None
        target = self.next
        crossed = (timestamp - target) // self.period
        self.missed += crossed
        self.next += (crossed + 1) * self.period
        return target

    def consume(self, frame):
        target = self.accept(frame.timestamp)
        return None if target is None else transform(frame, self.config, target)


def transform(frame, config, target=None):
    h, w = frame.pixels.shape[:2]
    scale = min(config.width / w, config.height / h)
    width, height = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cv2.resize(frame.pixels, (width, height), interpolation=cv2.INTER_AREA)
    left, top = (config.width-width)//2, (config.height-height)//2
    output = np.zeros((config.height, config.width, 3), dtype=np.uint8)
    output[top:top+height, left:left+width] = resized
    if config.color == "gray":
        output = cv2.cvtColor(output, cv2.COLOR_RGB2GRAY)
    output.setflags(write=False)
    return Sample(frame, frame.timestamp if target is None else target, output,
                  dict(scale_x=width/w, scale_y=height/h, left=left, top=top,
                       source_width=w, source_height=h))


def sample_index(source, config):
    sampler = Sampler(config)
    return [(i, target) for i, (_, _, timestamp) in enumerate(source.index)
            if (target := sampler.accept(timestamp)) is not None]


def enlarge(pixels, size=384, nearest=True):
    h, w = pixels.shape[:2]
    return cv2.resize(pixels, (max(1, round(w*size/max(h,w))), max(1, round(h*size/max(h,w)))),
                      interpolation=cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR)
