"""CLI: проверка озвучки медитации.

Примеры:
  # только звук (писк, артефакты, громкость, эмоции, паузы)
  python -m medqa audio.wav

  # звук + сверка с исходным текстом (нужен Whisper)
  python -m medqa audio.wav --script scenario.txt --transcribe

  # только проверка текста сценария до синтеза
  python -m medqa --script scenario.txt --check-text

  # сохранить машинный отчёт
  python -m medqa audio.wav --json report.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="medqa",
        description="Проверка качества AI-озвучки медитаций (Fish Audio и др.)",
    )
    p.add_argument("audio", nargs="?", help="Аудиофайл (.wav; .mp3/.m4a — при наличии soundfile)")
    p.add_argument("--script", help="Исходный текст сценария (.txt)")
    p.add_argument("--transcribe", action="store_true",
                   help="Расшифровать аудио Whisper и сверить с --script")
    p.add_argument("--check-text", action="store_true",
                   help="Проверить исходный текст (пробелы/пунктуация/латиница/числа)")
    p.add_argument("--check-stress", action="store_true",
                   help="Проставить ударения RUAccent (нужен пакет ruaccent)")
    p.add_argument("--model", default="large-v3", help="Модель Whisper (по умолч. large-v3)")
    p.add_argument("--language", default="ru", help="Язык расшифровки (по умолч. ru)")
    p.add_argument("--json", dest="json_out", help="Сохранить отчёт в JSON")
    args = p.parse_args(argv)

    if not args.audio and not args.script:
        p.error("укажи аудиофайл и/или --script")

    from . import report as R

    audio_issues = []
    transcript_issues = []
    text_issues = []
    duration = None

    # --- Трек содержания по тексту сценария ---
    script_text = None
    if args.script:
        script_text = Path(args.script).read_text(encoding="utf-8")
        if args.check_text:
            from .textcheck import check_text
            text_issues += check_text(script_text)
        if args.check_stress:
            from .textcheck import check_stress
            text_issues += check_stress(script_text)

    # --- Акустический трек ---
    if args.audio:
        from .audioio import load_audio
        from .analyze import analyze_audio

        x, sr = load_audio(args.audio)
        duration = len(x) / sr
        _, audio_issues = analyze_audio(x, sr)

        # --- Сверка с текстом через расшифровку ---
        if args.transcribe:
            if not script_text:
                p.error("--transcribe требует --script для сверки")
            from .transcript import transcribe, diff_against_script
            words = transcribe(args.audio, language=args.language, model=args.model)
            transcript_issues = diff_against_script(words, script_text)

    rep = R.build(audio_issues, transcript_issues, text_issues, duration)
    print(R.to_text(rep))

    if args.json_out:
        Path(args.json_out).write_text(R.to_json(rep), encoding="utf-8")
        print(f"  JSON-отчёт сохранён: {args.json_out}")

    # Ненулевой код, если что-то найдено — удобно для CI/скриптов.
    return 1 if (rep["n_findings"] or rep["n_text_findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
