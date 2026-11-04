"""Vision Lab website. Start it with:  python start.py"""
import os
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

from vision_lab.cache import NotAvailable
from vision_lab.camera import SimulatedCamera
from vision_lab.streams import STREAM_A, STREAM_B, derive, sample_indices
from vision_lab.video import VideoFile, list_videos, save_upload

DATA = Path(os.environ.get("VISION_LAB_DATA", Path(__file__).parent / "data"))
STREAMS = {s.name: s for s in (STREAM_A, STREAM_B)}
PAGE = 12  # thumbnails per gallery page

st.set_page_config(page_title="Vision Lab", layout="wide")


@st.cache_resource(max_entries=8)
def open_video(path: str) -> VideoFile:
    return VideoFile(path)


@st.cache_data(max_entries=8)
def gallery_page(path: str, stream: str, indices: tuple) -> list:
    """Derived images for one page, decoded in a single pass and kept only in memory."""
    wanted = set(indices)
    images = []
    for frame in open_video(path).frames(indices[0]):
        if frame.index in wanted:
            images.append(derive(frame, STREAMS[stream]).pixels)
        if frame.index >= indices[-1]:
            break
    return images


def enlarge(pixels, size=320):
    """Nearest-neighbour enlargement so individual pixels stay visible."""
    image = Image.fromarray(pixels)
    scale = max(1, size // max(image.size))
    return np.asarray(image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST))


def describe(name):
    s = STREAMS[name]
    return f"Stream {name}: {s.width}×{s.height} {'greyscale' if s.gray else 'colour'}, {s.fps} FPS"


def seconds(t):
    return f"{float(t):.3f} s"


# ---- Sidebar: upload and choose a video -------------------------------------------------------
with st.sidebar:
    st.header("Vision Lab")
    round_ = st.session_state.setdefault("upload_round", 0)
    uploads = st.file_uploader("Upload MP4/MOV videos", type=["mp4", "mov"], accept_multiple_files=True,
                               key=f"upload-{round_}", help="Up to 512 MB per file. Originals are never modified.")
    if uploads:
        for upload in uploads:
            with st.spinner(f"Saving {upload.name}…"):
                try:
                    save_upload(upload, upload.name, DATA)
                except ValueError as exc:
                    st.session_state.upload_error = f"{upload.name}: {exc}"
        st.session_state.upload_round += 1  # clears the upload box so files are saved once
        st.rerun()
    if error := st.session_state.pop("upload_error", None):
        st.error(error)
    videos = dict((str(path), name) for name, path in list_videos(DATA))
    if not videos:
        st.info("Upload a video from your phone to begin.")
        st.stop()
    path = st.selectbox("Video", list(videos), format_func=videos.get)

video = open_video(path)
st.subheader(videos[path])
st.caption(f"{video.width}×{video.height} · {video.codec} · {len(video.times)} frames · "
           f"{seconds(video.duration)} · {'variable' if video.variable_frame_rate else 'constant'} frame rate")
view = st.radio("View", ["Simulated camera", "Frame browser", "Original video"], horizontal=True,
                label_visibility="collapsed")

camera = st.session_state.get("camera")
if camera is None or camera.source is not video:
    camera = st.session_state.camera = SimulatedCamera(video)
if view != "Simulated camera":
    camera.pause()


# ---- Original video ---------------------------------------------------------------------------
if view == "Original video":
    st.video(path)
    st.caption("Played by your browser. Some browsers cannot play iPhone HEVC video; "
               "the other views decode on the server and still work.")


# ---- Simulated camera ---------------------------------------------------------------------------
def live_view():
    camera.update()
    span = camera.cache.span
    cols = st.columns(4)
    cols[0].metric("Simulated time", seconds(camera.time))
    cols[1].metric("Frames arrived", camera.arrived)
    cols[2].metric("Cached footage", "none" if span is None else f"{float(span[0]):.1f}–{float(span[1]):.1f} s")
    cols[3].metric("Last update took", f"{camera.update_seconds * 1000:.0f} ms")
    if camera.frame is not None:
        lag = camera.time - float(camera.frame.time)
        st.caption(f"Latest source frame #{camera.frame.index} at {seconds(camera.frame.time)} · "
                   f"processing lag {lag:.2f} s · missed stream slots "
                   + ", ".join(f"{n}: {s.missed}" for n, s in camera.samplers.items())
                   + (" · end of video" if camera.finished else ""))
        cols = st.columns([3, 2, 2])
        cols[0].image(camera.frame.resized(480, 480), caption="Source (preview size)")
        for col, name in zip(cols[1:], STREAMS):
            if sample := camera.latest.get(name):
                col.image(enlarge(sample.pixels, 256), output_format="PNG",
                          caption=f"{describe(name)} · frame #{sample.frame.index} at {seconds(sample.frame.time)}")


if view == "Simulated camera":
    st.caption("Replays the video as if it were a live camera: frames arrive at their recorded times.")
    cols = st.columns([1, 1, 1, 3])
    if cols[0].button("▶ Play", disabled=camera.playing or camera.finished):
        camera.play()
    if cols[1].button("⏸ Pause", disabled=not camera.playing):
        camera.pause()
    if cols[2].button("⟲ Restart"):
        camera.restart()
    speed = cols[3].select_slider("Speed", [0.25, 0.5, 1.0, 2.0, 4.0], value=camera.speed)
    if speed != camera.speed:
        camera.set_speed(speed)
    st.fragment(run_every=0.25 if camera.playing else None)(live_view)()

    st.markdown("**High-resolution rolling cache**")
    st.caption(f"Holds the last {float(camera.cache.seconds):.0f} s of footage that has arrived. "
               "Future or expired times are refused.")
    cols = st.columns([1, 3])
    lookup = cols[0].number_input("Time (s)", 0.0, float(video.duration), 0.0, step=0.5)
    if cols[0].button("Get frame from cache"):
        try:
            frame = camera.cache.get(lookup)
            cols[1].image(frame.pixels, caption=f"Frame #{frame.index} at {seconds(frame.time)} (full resolution)")
        except NotAvailable as exc:
            cols[1].warning(str(exc))


# ---- Frame browser ------------------------------------------------------------------------------
def select(key, value, count):
    value = min(max(value, 0), count - 1)
    st.session_state[key] = value
    st.session_state[key + "-page"] = value // PAGE + 1


if view == "Frame browser":
    st.caption("Browse every frame each stream takes from the whole recording. "
               "Images are generated on demand and kept only in memory.")
    name = st.radio("Stream", list(STREAMS), format_func=describe, horizontal=True)
    indices = sample_indices(video.times, STREAMS[name].fps)
    key = f"selected-{path}-{name}"
    st.session_state.setdefault(key, 0)
    st.session_state.setdefault(key + "-page", 1)
    pages = (len(indices) + PAGE - 1) // PAGE
    page = st.number_input(f"Page (of {pages})", 1, pages, key=key + "-page")
    on_page = indices[(page - 1) * PAGE:page * PAGE]
    cols = st.columns(6)
    for offset, (index, pixels) in enumerate(zip(on_page, gallery_page(path, name, tuple(on_page)))):
        position = (page - 1) * PAGE + offset
        with cols[offset % 6]:
            st.image(enlarge(pixels, 128), output_format="PNG")
            st.button(seconds(video.times[index]), key=f"tile-{key}-{position}", on_click=select,
                      args=(key, position, len(indices)),
                      type="primary" if position == st.session_state[key] else "secondary")

    selected = st.session_state[key]
    cols = st.columns([1, 1, 4])
    cols[0].button("◀ Previous", on_click=select, args=(key, selected - 1, len(indices)), disabled=selected == 0)
    cols[1].button("Next ▶", on_click=select, args=(key, selected + 1, len(indices)),
                   disabled=selected == len(indices) - 1)
    cols[2].caption(f"Sample {selected + 1} of {len(indices)}")

    frame = video.frame(indices[selected])
    sample = derive(frame, STREAMS[name])
    cols = st.columns([1, 2])
    cols[0].image(enlarge(sample.pixels), output_format="PNG", caption=f"Stream {name} · {sample.pixels.shape} {sample.pixels.dtype}")
    cols[1].image(frame.pixels, caption=f"Original frame #{frame.index} at {seconds(frame.time)} · "
                                        f"{frame.pixels.shape[1]}×{frame.pixels.shape[0]}")
    if selected > 0:
        previous = derive(video.frame(indices[selected - 1]), STREAMS[name])
        difference = np.abs(sample.pixels.astype(np.int16) - previous.pixels.astype(np.int16)).astype(np.uint8)
        cols = st.columns([1, 1, 2])
        cols[0].image(enlarge(previous.pixels), output_format="PNG", caption=f"Previous sample at {seconds(previous.frame.time)}")
        cols[1].image(enlarge(difference), output_format="PNG", caption="Absolute pixel difference (bright = changed)")
        cols[2].metric("Mean difference", f"{difference.mean():.1f} / 255")
        cols[2].metric("Pixels changed by more than 25", f"{(difference > 25).mean():.1%}")
