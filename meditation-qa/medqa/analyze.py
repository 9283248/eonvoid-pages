"""Акустические детекторы аномалий поверх покадровых признаков.

Все пороги адаптивные: считаем робастную статистику (медиана + MAD) по самой
дорожке, поэтому детекторы подстраиваются под конкретный голос и не требуют
ручной калибровки под каждого спикера.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .features import Frames, extract


@dataclass
class Issue:
    start: float                 # сек
    end: float                   # сек
    kind: str                    # squeak / glitch / clipping / loud / dropout / expressive / long_pause
    severity: float              # 0..1, для сортировки
    message: str                 # человекочитаемое описание (RU)
    detail: dict = field(default_factory=dict)

    @property
    def mid(self) -> float:
        return (self.start + self.end) / 2.0


def _mad(x: np.ndarray) -> float:
    if len(x) == 0:
        return 0.0
    med = np.median(x)
    return float(np.median(np.abs(x - med)) * 1.4826)  # ~ст.откл. для нормального


def _runs(mask: np.ndarray, min_len: int = 1, merge_gap: int = 0) -> list[tuple[int, int]]:
    """Индексные интервалы [start, end) подряд идущих True, с опц. склейкой близких."""
    runs: list[tuple[int, int]] = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    if merge_gap > 0 and runs:
        merged = [runs[0]]
        for s, e in runs[1:]:
            if s - merged[-1][1] <= merge_gap:
                merged[-1] = (merged[-1][0], e)
            else:
                merged.append((s, e))
        runs = merged
    return [(s, e) for s, e in runs if e - s >= min_len]


def _t(fr: Frames, idx: int) -> float:
    idx = int(np.clip(idx, 0, len(fr.times) - 1))
    return float(fr.times[idx])


# --------------------------------------------------------------------------- #
# Детекторы
# --------------------------------------------------------------------------- #

def detect_squeaks(fr: Frames) -> list[Issue]:
    """Голос ушёл в писк: F0 в вокализованных кадрах резко выше обычного диапазона."""
    voiced_f0 = fr.f0[fr.voiced]
    if len(voiced_f0) < 10:
        return []
    med = float(np.median(voiced_f0))
    mad = _mad(voiced_f0) or (med * 0.1)
    # Порог: заметно выше и медианы×1.6, и медиана+4·MAD (что строже).
    thr = max(med * 1.6, med + 4.0 * mad)

    mask = fr.voiced & (fr.f0 > thr)
    issues = []
    for s, e in _runs(mask, min_len=3, merge_gap=5):  # >= ~30 мс
        peak = float(fr.f0[s:e].max())
        sev = float(np.clip((peak / med - 1.4) / 1.2, 0.3, 1.0))
        issues.append(Issue(
            start=_t(fr, s), end=_t(fr, e - 1), kind="squeak", severity=sev,
            message=f"Возможный писк / срыв голоса вверх: тон ~{peak:.0f} Гц "
                    f"при обычных ~{med:.0f} Гц",
            detail={"peak_hz": round(peak, 1), "median_hz": round(med, 1)},
        ))
    return issues


def detect_glitches(fr: Frames) -> list[Issue]:
    """Артефакты/склейки: резкие спектральные скачки (flux) вне нормальных атак речи."""
    flux = fr.flux
    if len(flux) < 10:
        return []
    med = float(np.median(flux))
    mad = _mad(flux) or (med * 0.1 + 1e-6)
    thr = med + 8.0 * mad

    # Границы фраз (тишина↔голос) дают естественный всплеск flux — это не артефакт.
    prev = np.concatenate([[False], fr.voiced[:-1]])
    nxt = np.concatenate([fr.voiced[1:], [False]])
    boundary = (fr.voiced != prev) | (fr.voiced != nxt)
    boundary_win = boundary.copy()
    for shift in (1, 2):
        boundary_win[shift:] |= boundary[:-shift]
        boundary_win[:-shift] |= boundary[shift:]

    mask = (flux > thr) & ~boundary_win
    issues = []
    for s, e in _runs(mask, min_len=1, merge_gap=2):
        peak = float(flux[s:e].max())
        sev = float(np.clip((peak - thr) / (thr + 1e-6), 0.3, 1.0))
        issues.append(Issue(
            start=_t(fr, max(0, s - 1)), end=_t(fr, e), kind="glitch", severity=sev,
            message="Резкий спектральный скачок — возможен артефакт/щелчок/склейка",
            detail={"flux": round(peak, 4), "threshold": round(thr, 4)},
        ))
    return issues


def detect_clipping(x: np.ndarray, sr: int, hop: float = 0.01) -> list[Issue]:
    """Клиппинг: сэмплы упираются в максимум амплитуды."""
    clipped = np.abs(x) >= 0.999
    if not clipped.any():
        return []
    win = max(1, int(sr * hop))
    # Группируем клиппированные сэмплы по окнам.
    idx = np.where(clipped)[0]
    issues = []
    groups = _runs_from_indices(idx, gap=win)
    for s, e in groups:
        count = int(np.sum(clipped[s:e + 1]))
        if count < 3:
            continue
        issues.append(Issue(
            start=s / sr, end=e / sr, kind="clipping", severity=0.7,
            message=f"Клиппинг сигнала ({count} сэмплов на пределе амплитуды)",
            detail={"samples": count},
        ))
    return issues


def _runs_from_indices(idx: np.ndarray, gap: int) -> list[tuple[int, int]]:
    if len(idx) == 0:
        return []
    groups = []
    start = prev = idx[0]
    for k in idx[1:]:
        if k - prev > gap:
            groups.append((int(start), int(prev)))
            start = k
        prev = k
    groups.append((int(start), int(prev)))
    return groups


def detect_loudness(fr: Frames) -> list[Issue]:
    """Скачки громкости: внезапно слишком громко (крик) или провал (пропажа звука)."""
    rms = fr.rms
    voiced_rms = rms[fr.voiced]
    if len(voiced_rms) < 10:
        return []
    med = float(np.median(voiced_rms))
    mad = _mad(voiced_rms) or (med * 0.1 + 1e-9)

    issues = []
    loud_thr = med + 6.0 * mad
    for s, e in _runs((rms > loud_thr) & fr.voiced, min_len=3, merge_gap=5):
        peak = float(rms[s:e].max())
        issues.append(Issue(
            start=_t(fr, s), end=_t(fr, e - 1), kind="loud",
            severity=float(np.clip((peak / med - 1.5) / 2.0, 0.3, 0.9)),
            message=f"Резкий скачок громкости (×{peak / med:.1f} к средней)",
            detail={"rms": round(peak, 4), "median": round(med, 4)},
        ))
    return issues


def _voiced_phrases(fr: Frames, min_gap_s: float = 0.35, min_len_s: float = 0.6):
    """Фразы = вокализованные участки, разделённые паузами >= min_gap_s."""
    gap_frames = max(1, int(min_gap_s / (fr.hop / fr.sr)))
    runs = _runs(fr.voiced, min_len=1, merge_gap=gap_frames)
    min_len = int(min_len_s / (fr.hop / fr.sr))
    return [(s, e) for s, e in runs if e - s >= min_len]


def detect_expressive(fr: Frames) -> list[Issue]:
    """«Слишком восхищённо»: фразы с аномально высоким тоном/размахом/громкостью/темпом
    относительно спокойного базового уровня самой медитации."""
    phrases = _voiced_phrases(fr)
    if len(phrases) < 4:
        return []

    feats = []
    for s, e in phrases:
        f0 = fr.f0[s:e]
        f0 = f0[f0 > 0]
        if len(f0) < 3:
            feats.append(None)
            continue
        rms = fr.rms[s:e]
        # Темп: доля переходов вокализация↔пауза (проксик числа слогов/сек).
        v = fr.voiced[s:e].astype(np.int8)
        rate = float(np.mean(np.abs(np.diff(v)) > 0)) if len(v) > 1 else 0.0
        feats.append({
            "f0_mean": float(np.mean(f0)),
            "f0_range": float(np.percentile(f0, 90) - np.percentile(f0, 10)),
            "rms_mean": float(np.mean(rms)),
            "rate": rate,
        })

    valid = [(i, f) for i, f in enumerate(feats) if f is not None]
    if len(valid) < 4:
        return []

    def robust_z(key):
        vals = np.array([f[key] for _, f in valid])
        med = np.median(vals)
        mad = _mad(vals) or (np.std(vals) + 1e-9)
        return {i: (f[key] - med) / mad for i, f in valid}

    z = {k: robust_z(k) for k in ("f0_mean", "f0_range", "rms_mean", "rate")}

    issues = []
    for i, _ in valid:
        # Восхищённость = высокий тон + широкий размах + громче + быстрее.
        score = (z["f0_mean"][i] + z["f0_range"][i]
                 + 0.5 * z["rms_mean"][i] + 0.5 * z["rate"][i])
        if score > 4.0:  # заметный выброс относительно спокойного фона
            s, e = phrases[i]
            issues.append(Issue(
                start=_t(fr, s), end=_t(fr, e - 1), kind="expressive",
                severity=float(np.clip((score - 4.0) / 4.0, 0.3, 0.9)),
                message="Слишком эмоционально/восхищённо для медитации "
                        "(высокий тон и размах интонации)",
                detail={"score": round(float(score), 2)},
            ))
    return issues


def detect_long_pauses(fr: Frames, max_pause_s: float = 3.5) -> list[Issue]:
    """Слишком длинные паузы/провалы — иногда признак пропавшего фрагмента."""
    silent = ~fr.voiced & (fr.rms < (np.median(fr.rms[fr.voiced]) * 0.2
                                     if fr.voiced.any() else 1e-3))
    min_len = int(max_pause_s / (fr.hop / fr.sr))
    issues = []
    for s, e in _runs(silent, min_len=min_len):
        dur = _t(fr, e - 1) - _t(fr, s)
        issues.append(Issue(
            start=_t(fr, s), end=_t(fr, e - 1), kind="long_pause",
            severity=0.35,
            message=f"Длинная пауза {dur:.1f} с — проверь, не пропущен ли фрагмент",
            detail={"duration_s": round(dur, 2)},
        ))
    return issues


def analyze_audio(x: np.ndarray, sr: int) -> tuple[Frames, list[Issue]]:
    """Полный акустический проход. Возвращает признаки и отсортированные находки."""
    fr = extract(x, sr)
    issues: list[Issue] = []
    issues += detect_clipping(x, sr)
    issues += detect_squeaks(fr)
    issues += detect_glitches(fr)
    issues += detect_loudness(fr)
    issues += detect_expressive(fr)
    issues += detect_long_pauses(fr)
    issues.sort(key=lambda i: i.start)
    return fr, issues
