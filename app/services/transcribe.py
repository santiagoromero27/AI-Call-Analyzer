"""
Download a call recording and transcribe it with faster-whisper.

Stereo recordings are split into two mono channels so each side gets its own
label (caller / agent).  Which channel is the caller is controlled by the
CALLER_CHANNEL env var (0 = left, 1 = right).  Mono recordings fall back to
a single "unknown" speaker label.

Audio decoding uses PyAV (bundled with faster-whisper wheels — no system ffmpeg
required) so pydub is not a dependency.
"""
import os
import tempfile
import wave

import av
import numpy as np
import requests
from faster_whisper import WhisperModel

from ..config import settings

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def _download(url: str) -> str:
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    suffix = url.split("?")[0].rsplit(".", 1)[-1]
    if suffix not in ("mp3", "wav", "m4a", "ogg", "flac", "mp4", "webm"):
        suffix = "wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}")
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def _decode_channels(path: str) -> tuple[list[np.ndarray], int]:
    """Decode audio file into a list of float32 mono channel arrays + sample rate.

    av 17 removed AudioFrame.reformat(); use AudioResampler instead.
    """
    container = av.open(path)
    audio_stream = container.streams.audio[0]
    sample_rate = audio_stream.sample_rate

    resampler = av.AudioResampler(format="fltp")  # planar float32, keeps original layout/rate
    frames: list[np.ndarray] = []

    for frame in container.decode(audio_stream):
        for rf in resampler.resample(frame):
            frames.append(rf.to_ndarray())        # (n_channels, n_samples_per_frame)

    for rf in resampler.resample(None):           # flush
        frames.append(rf.to_ndarray())

    container.close()

    if not frames:
        return [np.array([], dtype=np.float32)], sample_rate

    merged = np.concatenate(frames, axis=1)       # (n_channels, total_samples)
    return [merged[i] for i in range(merged.shape[0])], sample_rate


def _write_mono_wav(data: np.ndarray, sample_rate: int) -> str:
    """Write a float32 mono array to a temp 16-bit WAV and return its path."""
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return path


def _transcribe_mono_wav(wav_path: str, label: str) -> list[dict]:
    segs, _ = _get_model().transcribe(wav_path, beam_size=5)
    return [
        {
            "speaker": label,
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
        }
        for s in segs
        if s.text.strip()
    ]


def transcribe(local_path: str) -> list[dict]:
    """Transcribe a local audio file. Returns time-sorted segment list."""
    channels, sample_rate = _decode_channels(local_path)

    if len(channels) >= 2:
        caller_idx = settings.CALLER_CHANNEL   # 0 or 1
        labels = {caller_idx: "caller", 1 - caller_idx: "agent"}

        segments: list[dict] = []
        for idx in (0, 1):
            wav_path = _write_mono_wav(channels[idx], sample_rate)
            try:
                segments.extend(_transcribe_mono_wav(wav_path, labels[idx]))
            finally:
                os.unlink(wav_path)

        segments.sort(key=lambda s: s["start"])
        return segments

    # mono fallback
    wav_path = _write_mono_wav(channels[0], sample_rate)
    try:
        return _transcribe_mono_wav(wav_path, "unknown")
    finally:
        os.unlink(wav_path)


def download_and_transcribe(url: str) -> tuple[str, list[dict]]:
    """Download from URL, transcribe, return (local_path, segments).
    Caller is responsible for unlinking local_path when done."""
    local = _download(url)
    try:
        segments = transcribe(local)
        return local, segments
    except Exception:
        os.unlink(local)
        raise
