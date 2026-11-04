"""Video decoding, derived streams, rolling cache and simulated camera."""
import hashlib
import io
import shutil
import subprocess
from fractions import Fraction

import numpy as np
import pytest

from vision_lab.cache import NotAvailable, RollingCache
from vision_lab.camera import SimulatedCamera
from vision_lab.streams import STREAM_A, STREAM_B, Sampler, StreamConfig, derive, sample_indices
from vision_lab.video import Frame, VideoFile, list_videos, save_upload


def test_decoding_uses_exact_timestamps(video30, vfr):
    video = VideoFile(video30)
    assert video.codec == "h264" and (video.width, video.height) == (160, 90)
    assert video.times == [Fraction(i, 30) for i in range(90)]  # B-frames reordered correctly
    assert not video.variable_frame_rate
    frames = list(video.frames())
    assert [f.index for f in frames] == list(range(90))
    assert [f.time for f in frames] == video.times
    assert frames[0].pixels.shape == (90, 160, 3) and not frames[0].pixels.flags.writeable

    odd = VideoFile(vfr)  # first timestamp 1.0 s becomes time 0
    assert odd.times == [Fraction(x) for x in ("0", "0.1", "0.25", "0.5", "0.9", "1")]
    assert odd.variable_frame_rate


def test_random_access_matches_sequential_decoding(video30):
    video = VideoFile(video30)
    frames = list(video.frames())
    for index in (0, 1, 17, 46, 89):
        frame = video.frame(index)
        assert frame.time == frames[index].time
        assert np.array_equal(frame.pixels, frames[index].pixels)
    with pytest.raises(IndexError):
        video.frame(90)


def test_original_file_is_never_modified(video30):
    before = hashlib.sha256(video30.read_bytes()).hexdigest()
    camera = SimulatedCamera(VideoFile(video30), clock=lambda: 0.0)
    camera.set_speed(1000)  # instantly reach the end
    camera.play()
    camera.clock = lambda: 1.0
    while not camera.finished:
        camera.update()
    assert hashlib.sha256(video30.read_bytes()).hexdigest() == before


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs the ffmpeg command")
def test_phone_rotation_is_applied(video30, tmp_path):
    rotated = tmp_path / "portrait.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-display_rotation", "90", "-i", str(video30),
                    "-c", "copy", str(rotated)], check=True)
    pixels = VideoFile(rotated).frame(0).pixels
    assert pixels.shape == (160, 90, 3)  # portrait, as the phone displayed it
    # Same orientation as FFmpeg's own automatic rotation.
    reference = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(rotated), "-frames:v", "1",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    reference = np.frombuffer(reference, np.uint8).reshape(pixels.shape)
    assert np.abs(pixels.astype(int) - reference).mean() < 3
    # The fast FFmpeg shrink (used while streaming) gives the same picture as shrinking full pixels.
    streamed = next(VideoFile(rotated).frames())
    fast = derive(streamed, STREAM_B).pixels
    slow = derive(Frame(0, Fraction(0), pixels), STREAM_B).pixels
    assert fast.shape == slow.shape == (320, 320, 3) and np.abs(fast.astype(int) - slow).mean() < 3


def test_stream_resolution_colour_and_rate(video30):
    video = VideoFile(video30)
    a = sample_indices(video.times, STREAM_A.fps)
    b = sample_indices(video.times, STREAM_B.fps)
    assert a == list(range(0, 90, 2))  # 15 of 30 frames per second
    assert b == [0, 30, 60]            # 1 per second
    frame = video.frame(30)
    sample_a, sample_b = derive(frame, STREAM_A), derive(frame, STREAM_B)
    assert sample_a.pixels.shape == (64, 64) and sample_a.pixels.dtype == np.uint8
    assert sample_b.pixels.shape == (320, 320, 3)
    assert sample_a.frame is sample_b.frame  # both streams share the source frame and time
    # 160×90 letterboxed into 320×320: 320×180 picture with 70-pixel black bars.
    assert not sample_b.pixels[:70].any() and not sample_b.pixels[-70:].any()
    assert sample_b.pixels[70:250].any()


def test_greyscale_uses_rgb_order():
    red = np.zeros((10, 10, 3), dtype=np.uint8)
    red[..., 0] = 255
    sample = derive(Frame(0, Fraction(0), red), StreamConfig("t", 10, 10, gray=True, fps=1))
    assert np.all(sample.pixels == 76)  # luminance of red, not of blue


def test_sampling_gaps_and_rates_above_source(vfr):
    times = VideoFile(vfr).times  # 0, .1, .25, .5, .9, 1
    assert sample_indices(times, 4) == [0, 2, 3, 4, 5]
    assert sample_indices(times, 120) == list(range(6))  # never duplicates frames
    sampler = Sampler(4)
    for t in times:
        sampler.accept(t)
    assert sampler.missed == 0
    sampler = Sampler(10)
    for t in times:
        sampler.accept(t)
    assert sampler.missed == 5  # slots 0.3, 0.4, 0.6, 0.7, 0.8 had no frame of their own


def test_cache_refuses_future_and_expired_footage(video30):
    video = VideoFile(video30)
    cache = RollingCache(video, seconds=1)
    with pytest.raises(NotAvailable):
        cache.get(0)
    frames = list(video.frames())
    for frame in frames[:31]:  # arrived up to 1.0 s
        cache.add(frame)
    assert cache.get(Fraction(1, 2)).index == 15
    assert cache.get(0.51).index == 15  # latest frame at or before the time
    with pytest.raises(NotAvailable, match="not arrived"):
        cache.get(1.01)
    for frame in frames[31:46]:  # arrived up to 1.5 s: window is now 0.5–1.5 s
        cache.add(frame)
    assert cache.span == (Fraction(1, 2), Fraction(3, 2)) and len(cache) == 31
    with pytest.raises(NotAvailable, match="no longer cached"):
        cache.get(0.49)
    assert cache.get(1.5).pixels.shape == (90, 160, 3)  # full resolution
    cache.clear()
    with pytest.raises(NotAvailable):
        cache.get(1)


def test_camera_follows_recorded_time(video30):
    now = [100.0]
    camera = SimulatedCamera(VideoFile(video30), clock=lambda: now[0])
    assert camera.update() == [] and camera.arrived == 0  # paused: nothing arrives
    camera.play()
    samples = camera.update()
    assert camera.arrived == 1 and [s.stream for s in samples] == ["A", "B"]
    now[0] += 0.5
    camera.update()
    assert camera.frame.time == Fraction(1, 2) and camera.arrived == 16
    assert camera.latest["A"].frame.index == 14 and camera.latest["B"].frame.index == 0
    with pytest.raises(NotAvailable):
        camera.cache.get(0.6)  # the future is not available yet
    camera.pause()
    now[0] += 10
    assert camera.update() == [] and camera.time == 0.5  # pause freezes time
    camera.play()
    camera.set_speed(2)
    now[0] += 0.25  # 0.5 simulated seconds
    camera.update()
    assert camera.frame.time == 1 and camera.latest["B"].frame.index == 30
    camera.restart()
    assert camera.arrived == 0 and camera.cache.span is None and not camera.latest and camera.time == 0


def test_camera_matches_offline_sampling(video30):
    camera = SimulatedCamera(VideoFile(video30), clock=lambda: 0.0)
    camera.set_speed(10_000)
    camera.play()
    camera.clock = lambda: 1.0
    samples = []
    while not camera.finished:
        samples += camera.update(limit=7)
    for config in (STREAM_A, STREAM_B):
        assert [s.frame.index for s in samples if s.stream == config.name] == \
            sample_indices(camera.source.times, config.fps)


def test_upload_storage(video30, tmp_path):
    data = tmp_path / "data"
    path = save_upload(io.BytesIO(video30.read_bytes()), "My clip.MP4", data)
    assert path.name == "original.mp4" and path.read_bytes() == video30.read_bytes()
    save_upload(io.BytesIO(video30.read_bytes()), "My clip.MP4", data)  # same name: stored separately
    assert [name for name, _ in list_videos(data)] == ["My clip.MP4", "My clip.MP4"]
    with pytest.raises(ValueError, match="MP4 or MOV"):
        save_upload(io.BytesIO(b"x"), "notes.txt", data)
    with pytest.raises(ValueError, match="Could not read"):
        save_upload(io.BytesIO(b"not a video"), "broken.mov", data)
    assert len(list((data / "videos").iterdir())) == 2  # the broken upload was cleaned up


def test_videos_from_the_previous_version_still_appear(video30, tmp_path):
    """Earlier uploads (with annotations from the removed labelling tools) are listed and left untouched."""
    folder = tmp_path / "data" / "videos" / "0b5c7c1e-1111-4222-8333-944445555666"
    folder.mkdir(parents=True)
    shutil.copy(video30, folder / "original.mov")
    (folder / "metadata.json").write_text('{"id": "0b5c7c1e-1111-4222-8333-944445555666", "name": "Old clip", '
                                          '"extension": ".mov", "notes": "", "duration": 3.0}')
    (folder / "annotations.json").write_text('{"motion": "Yes", "intervals": []}')
    assert list_videos(tmp_path / "data") == [("Old clip", folder / "original.mov")]
    assert (folder / "annotations.json").read_text() == '{"motion": "Yes", "intervals": []}'
