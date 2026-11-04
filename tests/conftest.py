from fractions import Fraction

import av
import numpy as np
import pytest


def make_video(path, times_ms, size=(64, 48), codec="mpeg4"):
    """Small synthetic video: a white square moves one step per frame. Frame i has red value i."""
    width, height = size
    with av.open(str(path), "w") as container:
        stream = container.add_stream(codec, rate=30)
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
        for i, t in enumerate(times_ms):
            pixels = np.full((height, width, 3), 20, dtype=np.uint8)
            x = (i * 4) % (width - 8)
            pixels[8:16, x:x + 8] = 230
            image = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            image.pts, image.time_base = t, Fraction(1, 1000)
            for packet in stream.encode(image):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def make_phone_video(path):
    """3 seconds at exactly 30 FPS in a 1/90000 time base, as phones record, with B-frames (H.264)."""
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=30, options={"bf": "2", "g": "15"})
        stream.width, stream.height, stream.pix_fmt = 160, 90, "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 90000)
        for i in range(90):
            pixels = np.full((90, 160, 3), 20, dtype=np.uint8)
            pixels[30:50, i:i + 20] = 230
            image = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            image.pts, image.time_base = i * 3000, Fraction(1, 90000)
            for packet in stream.encode(image):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


@pytest.fixture
def video30(tmp_path):
    return make_phone_video(tmp_path / "phone.mp4")


@pytest.fixture
def vfr(tmp_path):
    """Variable frame rate MOV whose first timestamp is not zero."""
    return make_video(tmp_path / "vfr.mov", [1000, 1100, 1250, 1500, 1900, 2000])
