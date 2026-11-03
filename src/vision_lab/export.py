"""On-demand timestamped frame exports; no permanent PNG gallery."""
import json
from pathlib import Path
import tempfile
import zipfile
from PIL import Image
from vision_lab.streams import Sampler


def export_frames(source, config, start, end, destination):
    if not 0 <= start <= end <= float(source.duration):
        raise ValueError("Invalid export range")
    destination = Path(destination)
    sampler = Sampler(config)
    records = []
    # Streaming ZIP writes keep decoded image memory bounded.
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for frame in source.frames():
            if float(frame.timestamp) > end:
                break
            target = sampler.accept(frame.timestamp)
            if target is None or float(frame.timestamp) < start:
                continue
            from vision_lab.streams import transform
            sample = transform(frame, config, target)
            filename = f"frame_{frame.sequence:08d}_t{float(frame.timestamp):012.6f}.png"
            with archive.open(filename, 'w') as handle:
                Image.fromarray(sample.pixels).save(handle, format='PNG')
            records.append(dict(file=filename, sequence=frame.sequence, pts=frame.pts,
                                time_base=str(frame.time_base), timestamp=str(frame.timestamp),
                                target=str(target)))
        archive.writestr('timestamps.json', json.dumps(records, indent=2))
    return destination
