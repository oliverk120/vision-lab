"""Video source: read-only decoding of MP4/MOV files with exact timestamps, plus upload storage."""
import hashlib
import json
import shutil
import uuid
from fractions import Fraction
from functools import cached_property
from pathlib import Path

import av
import numpy as np
from PIL import Image


class Frame:
    """One source frame.

    `index` is the frame's position in presentation order and `time` is exact seconds since the
    first frame, taken from the file's presentation timestamps (never from a nominal frame rate).
    RGB `pixels` are converted only when first used, because most frames never need them.
    A live camera would create Frames directly from a NumPy array.
    """

    def __init__(self, index: int, time: Fraction, image):
        self.index, self.time, self._image = index, time, image

    @cached_property
    def pixels(self) -> np.ndarray:
        if isinstance(self._image, np.ndarray):
            pixels = self._image
        else:
            pixels = self._image.to_ndarray(format="rgb24")
            turns = round(self._image.rotation) % 360 // 90  # phone orientation metadata
            if turns:
                pixels = np.ascontiguousarray(np.rot90(pixels, turns))
        pixels.setflags(write=False)
        return pixels

    def resized(self, width: int, height: int) -> np.ndarray:
        """RGB pixels scaled to fit inside width×height, keeping the shape of the picture.

        For decoded video, FFmpeg scales directly from the compressed colour format, which is far
        faster than converting the full-resolution frame first.
        """
        if isinstance(self._image, np.ndarray) or "pixels" in self.__dict__:
            image = Image.fromarray(self.pixels)
            scale = min(width / image.width, height / image.height)
            size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            return np.asarray(image.resize(size, Image.Resampling.BOX))
        turns = round(self._image.rotation) % 360 // 90
        w, h = (self._image.height, self._image.width) if turns % 2 else (self._image.width, self._image.height)
        scale = min(width / w, height / h)
        w, h = max(1, round(w * scale)), max(1, round(h * scale))
        if turns % 2:
            w, h = h, w
        pixels = self._image.reformat(w, h, "rgb24", interpolation="AREA").to_ndarray()
        return np.ascontiguousarray(np.rot90(pixels, turns)) if turns else pixels


class VideoFile:
    """A recorded video, opened read-only. The original file is never modified.

    Anything offering `frames()` (Frames in time order) and `frame(index)` can replace it,
    for example a live camera keeping its recent frames.
    """

    def __init__(self, path):
        self.path = Path(path)
        with av.open(str(self.path)) as container:
            if not container.streams.video:
                raise ValueError("The file has no video track")
            stream = container.streams.video[0]
            # Reading packets (without decoding) is fast and gives every frame's timestamp.
            pts = sorted(p.pts for p in container.demux(stream) if p.pts is not None and not p.is_discard)
            self.codec, self.time_base = stream.codec_context.name, stream.time_base
        if not pts:
            raise ValueError("The video contains no frames")
        self._pts = pts
        self._index = {p: i for i, p in enumerate(pts)}
        self.times = [(p - pts[0]) * self.time_base for p in pts]
        self.duration = self.times[-1]
        self.variable_frame_rate = len({b - a for a, b in zip(self.times, self.times[1:])}) > 1
        # Decoding the first frame proves the file is readable and gives the size as displayed.
        self.height, self.width = self.frame(0).pixels.shape[:2]

    def frames(self, start: int = 0, seek: bool = True):
        """Yield frames in presentation order, beginning at frame number `start`."""
        with av.open(str(self.path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            if start and seek:
                container.seek(self._pts[start], stream=stream)  # jumps to the keyframe at or before
            for image in container.decode(stream):
                index = self._index.get(image.pts)
                if index is not None and index >= start:
                    yield Frame(index, self.times[index], image)

    def frame(self, index: int) -> Frame:
        """Random access to one frame."""
        if not 0 <= index < len(self.times):
            raise IndexError(f"Frame {index} does not exist")
        for seek in (True, False):  # if a keyframe seek overshoots, decode from the beginning
            frames = self.frames(index, seek)
            frame = next(frames, None)
            if frame is not None and frame.index == index:
                frame.pixels  # convert while the file is still open
                frames.close()
                return frame
            frames.close()
        raise IndexError(f"Frame {index} could not be decoded")


def save_upload(upload, name: str, root) -> Path:
    """Store an uploaded file as data/videos/<id>/original.<ext>; never overwrites anything."""
    suffix = Path(name).suffix.lower()
    if suffix not in (".mp4", ".mov"):
        raise ValueError("Please upload an MP4 or MOV file")
    folder = Path(root) / "videos" / str(uuid.uuid4())
    folder.mkdir(parents=True)
    path = folder / f"original{suffix}"
    digest = hashlib.sha256()
    with path.open("xb") as output:
        while block := upload.read(1 << 20):
            digest.update(block)
            output.write(block)
    try:
        VideoFile(path)
    except Exception as exc:
        shutil.rmtree(folder)  # only the folder created above
        raise ValueError(f"Could not read this video ({exc})") from exc
    metadata = {"id": folder.name, "name": Path(name).name, "extension": suffix, "sha256": digest.hexdigest()}
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return path


def list_videos(root) -> list[tuple[str, Path]]:
    """(name, path) of every stored video, sorted by name."""
    videos = []
    for metadata_path in Path(root).glob("videos/*/metadata.json"):
        metadata = json.loads(metadata_path.read_text())
        path = metadata_path.parent / f"original{metadata['extension']}"
        if path.exists():
            videos.append((metadata["name"], path))
    return sorted(videos)
