"""Сборка единого отчёта из акустических, текстовых и content-находок."""
from __future__ import annotations

import json
from dataclasses import asdict


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    m, s = divmod(seconds, 60.0)
    return f"{int(m):02d}:{s:04.1f}"


_LABELS = {
    "squeak": "ПИСК/СРЫВ",
    "glitch": "АРТЕФАКТ",
    "clipping": "КЛИППИНГ",
    "loud": "ГРОМКОСТЬ",
    "dropout": "ПРОВАЛ",
    "expressive": "ЭМОЦИЯ",
    "long_pause": "ПАУЗА",
    "missing": "ПРОПУСК",
    "extra": "ЛИШНЕЕ",
    "substitution": "ЧТЕНИЕ",
}


def build(audio_issues=None, transcript_issues=None, text_issues=None,
          duration: float | None = None) -> dict:
    """Единая структура отчёта (для JSON и для печати)."""
    findings = []
    for it in (audio_issues or []):
        findings.append({
            "t_start": round(it.start, 2), "t_end": round(it.end, 2),
            "track": "audio", "kind": it.kind, "severity": round(it.severity, 2),
            "message": it.message, "detail": it.detail,
        })
    for it in (transcript_issues or []):
        findings.append({
            "t_start": round(it.start, 2), "t_end": round(it.end, 2),
            "track": "content", "kind": it.kind, "severity": 0.6,
            "message": it.message, "detail": it.detail,
        })
    findings.sort(key=lambda f: f["t_start"])

    text_findings = [asdict(t) for t in (text_issues or [])]

    return {
        "duration_s": round(duration, 2) if duration else None,
        "n_findings": len(findings),
        "n_text_findings": len(text_findings),
        "findings": findings,
        "text_findings": text_findings,
    }


def to_text(report: dict) -> str:
    lines = []
    dur = report.get("duration_s")
    head = "═" * 60
    lines.append(head)
    lines.append("  ОТЧЁТ ПРОВЕРКИ ОЗВУЧКИ МЕДИТАЦИИ")
    if dur:
        lines.append(f"  Длительность: {fmt_time(dur)}")
    lines.append(head)

    findings = report["findings"]
    if not findings:
        lines.append("\n  ✓ Аудио-аномалий не найдено.")
    else:
        lines.append(f"\n  Найдено меток по звуку/содержанию: {len(findings)}\n")
        for f in findings:
            label = _LABELS.get(f["kind"], f["kind"].upper())
            sev = "!" * (1 + int(f["severity"] * 2))
            lines.append(f"  [{fmt_time(f['t_start'])}–{fmt_time(f['t_end'])}] "
                         f"{label:<10} {sev:<3} {f['message']}")

    tf = report["text_findings"]
    if tf:
        lines.append("\n" + "─" * 60)
        lines.append(f"  ПРОВЕРКА ИСХОДНОГО ТЕКСТА: {len(tf)} замечаний\n")
        for t in tf:
            lines.append(f"  строка {t['line']}:{t['col']}  [{t['kind']}] {t['message']}")
            if t.get("excerpt"):
                lines.append(f"      …{t['excerpt']}")
    lines.append("")
    return "\n".join(lines)


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
