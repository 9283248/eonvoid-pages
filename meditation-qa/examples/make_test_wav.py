"""Генерирует синтетический WAV с намеренными дефектами для проверки детекторов.

Создаёт «речеподобный» сигнал (тон ~130 Гц с формантами и паузами между
фразами) и вставляет: писк на 2.0 с, щелчок на 3.5 с, клиппинг на 5.0 с,
громкий всплеск на 6.5 с. Запуск:  python examples/make_test_wav.py
"""
import wave
from pathlib import Path

import numpy as np


def voiced(t, f0=130.0):
    # Голосоподобный сигнал: основной тон + гармоники (форманты).
    sig = np.zeros_like(t)
    for k, amp in [(1, 1.0), (2, 0.5), (3, 0.33), (5, 0.15), (8, 0.08)]:
        sig += amp * np.sin(2 * np.pi * f0 * k * t)
    return sig / 2.2


def main():
    sr = 16000
    dur = 8.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    x = np.zeros_like(t)

    # Спокойная «речь»: чередуем фразы и паузы.
    phrase = (np.sin(2 * np.pi * 0.7 * t) > -0.2).astype(np.float32)
    x = voiced(t, 130.0) * phrase * 0.3

    def idx(sec):
        return int(sec * sr)

    # 1) Писк на 2.0–2.25 с — тон уходит к 900 Гц.
    a, b = idx(2.0), idx(2.25)
    tt = t[a:b] - t[a]
    x[a:b] = 0.35 * np.sin(2 * np.pi * 900 * tt)

    # 2) Щелчок/артефакт на 3.5 с — короткий широкополосный импульс.
    c = idx(3.5)
    x[c:c + 40] += 0.6 * np.hanning(40)

    # 3) Клиппинг на 5.0–5.1 с.
    d, e = idx(5.0), idx(5.1)
    x[d:e] = voiced(t[d:e], 140.0) * 3.0  # перегруз → обрежется ниже

    # 4) Громкий всплеск на 6.5–6.7 с.
    f, g = idx(6.5), idx(6.7)
    x[f:g] = voiced(t[f:g], 150.0) * 1.2

    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767).astype(np.int16)

    out = Path(__file__).parent / "test_defective.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    print(f"Готово: {out}")


if __name__ == "__main__":
    main()
