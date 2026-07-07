"""Покадровые признаки сигнала (только numpy).

Одна функция `extract` режет сигнал на кадры и считает для каждого:
  - rms            — громкость (энергия)
  - f0             — основной тон, Гц (0 = невокализованный/тишина)
  - voiced         — есть ли голос в кадре
  - zcr            — доля переходов через ноль (шумность/фрикативы)
  - centroid       — спектральный центроид, Гц (яркость тембра)
  - flux           — спектральный поток (резкость изменения спектра, клики/склейки)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Frames:
    sr: int
    hop: int
    win: int
    times: np.ndarray      # центр каждого кадра, сек
    rms: np.ndarray
    f0: np.ndarray
    voiced: np.ndarray     # bool
    zcr: np.ndarray
    centroid: np.ndarray
    flux: np.ndarray


def _autocorr_f0(frame: np.ndarray, sr: int, fmin: float, fmax: float) -> float:
    """Оценка основного тона кадра по автокорреляции. 0.0 если тон не найден."""
    frame = frame - frame.mean()
    energy = float(np.dot(frame, frame))
    if energy < 1e-7:
        return 0.0

    corr = np.correlate(frame, frame, mode="full")[len(frame) - 1:]
    min_lag = int(sr / fmax)
    max_lag = int(sr / fmin)
    max_lag = min(max_lag, len(corr) - 1)
    if max_lag <= min_lag:
        return 0.0

    segment = corr[min_lag:max_lag]
    peak = int(np.argmax(segment)) + min_lag
    # Порог периодичности: пик автокорреляции должен быть заметным относительно нуля.
    if corr[peak] < 0.3 * corr[0]:
        return 0.0

    # Параболическая интерполяция вокруг пика для суб-сэмпловой точности.
    if 0 < peak < len(corr) - 1:
        a, b, c = corr[peak - 1], corr[peak], corr[peak + 1]
        denom = a - 2 * b + c
        if abs(denom) > 1e-9:
            peak = peak + 0.5 * (a - c) / denom
    return float(sr / peak) if peak > 0 else 0.0


def extract(
    x: np.ndarray,
    sr: int,
    win_ms: float = 40.0,
    hop_ms: float = 10.0,
    fmin: float = 70.0,
    fmax: float = 800.0,
) -> Frames:
    win = max(256, int(sr * win_ms / 1000.0))
    hop = max(64, int(sr * hop_ms / 1000.0))
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))

    window = np.hanning(win).astype(np.float32)
    n_frames = 1 + (len(x) - win) // hop

    rms = np.zeros(n_frames, dtype=np.float32)
    f0 = np.zeros(n_frames, dtype=np.float32)
    zcr = np.zeros(n_frames, dtype=np.float32)
    centroid = np.zeros(n_frames, dtype=np.float32)
    flux = np.zeros(n_frames, dtype=np.float32)

    freqs = np.fft.rfftfreq(win, d=1.0 / sr)
    prev_mag = None

    for i in range(n_frames):
        start = i * hop
        seg = x[start:start + win]
        rms[i] = float(np.sqrt(np.mean(seg ** 2)))
        zcr[i] = float(np.mean(np.abs(np.diff(np.sign(seg))) > 0))

        wseg = seg * window
        mag = np.abs(np.fft.rfft(wseg))
        mag_sum = mag.sum()
        if mag_sum > 1e-8:
            centroid[i] = float((freqs * mag).sum() / mag_sum)
        if prev_mag is not None:
            diff = mag - prev_mag
            flux[i] = float(np.sqrt(np.mean(diff ** 2)))
        prev_mag = mag

        f0[i] = _autocorr_f0(seg, sr, fmin, fmax)

    times = (np.arange(n_frames) * hop + win / 2) / sr
    # Порог вокализации: достаточно громко и найден тон.
    rms_gate = max(1e-4, float(np.median(rms[rms > 0]) * 0.15)) if np.any(rms > 0) else 1e-4
    voiced = (f0 > 0) & (rms > rms_gate)

    return Frames(
        sr=sr, hop=hop, win=win, times=times,
        rms=rms, f0=f0, voiced=voiced, zcr=zcr, centroid=centroid, flux=flux,
    )
