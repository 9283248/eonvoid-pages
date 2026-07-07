"""Загрузка аудио в моно float32 без тяжёлых зависимостей.

WAV читается стандартным модулем `wave`. Для mp3/m4a/ogg — если установлен
`soundfile`, используем его; иначе просим сконвертировать в WAV (ffmpeg).
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def _read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        sr = w.getframerate()
        frames = w.readframes(w.getnframes())

    if sampwidth == 2:
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sampwidth == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Неподдерживаемая разрядность WAV: {sampwidth * 8} бит")

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    return data, sr


def _read_soundfile(path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf  # опционально

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    return data.mean(axis=1), sr


def load_audio(path: str, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    """Возвращает (сигнал моно float32 в [-1, 1], частота дискретизации)."""
    ext = Path(path).suffix.lower()
    if ext == ".wav":
        try:
            data, sr = _read_wav(path)
        except Exception:
            data, sr = _read_soundfile(path)
    else:
        try:
            data, sr = _read_soundfile(path)
        except ImportError as e:
            raise RuntimeError(
                f"Файл {ext} требует пакет soundfile или конвертации в WAV. "
                f"Установи `pip install soundfile` или запусти "
                f"`ffmpeg -i \"{path}\" \"{Path(path).with_suffix('.wav')}\"`."
            ) from e

    if target_sr and sr != target_sr:
        data = _resample(data, sr, target_sr)
        sr = target_sr
    return data.astype(np.float32), sr


def _resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Линейная передискретизация. Для анализа тона/энергии точности хватает."""
    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    if n_out <= 1:
        return x
    t_in = np.linspace(0.0, 1.0, num=len(x), endpoint=False)
    t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(t_out, t_in, x)
