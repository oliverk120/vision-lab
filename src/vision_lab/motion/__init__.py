"""Plugin contract and synthetic demonstration only: no real motion detection."""
from dataclasses import dataclass, field
from typing import Protocol
import numpy as np
from vision_lab.streams import Sample


@dataclass
class Prediction:
    detected: bool
    score: float | None = None
    mask: np.ndarray | None = None
    debug: dict[str, np.ndarray] = field(default_factory=dict)


class Detector(Protocol):
    name: str
    version: str
    def reset(self) -> None: ...
    def process(self, sample: Sample) -> Prediction: ...


class SyntheticDetector:
    """Timestamp-only fixture. Does not analyze pixels or establish accuracy."""
    version = '1'
    def __init__(self, name, config):
        self.name = name
        self.config = dict(config)
        period = float(self.config.get('period_seconds',4))
        if not np.isfinite(period) or period <= 0:
            raise ValueError('Mock period must be positive')
        self.reset()

    def reset(self):
        self.count = 0

    def process(self, sample):
        self.count += 1
        period = float(self.config.get('period_seconds',4))
        positive = (self.name == 'mock_always' or
                    (self.name == 'mock_pulse' and float(sample.frame.timestamp) % period < period/2))
        return Prediction(positive, 1.0 if positive else 0.0)


# Agents add a factory here without changing ingestion, storage, or scoring.
REGISTRY = {name: (lambda config, name=name: SyntheticDetector(name, config))
            for name in ('mock_pulse','mock_always','mock_never')}
