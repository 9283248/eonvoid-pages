"""Опциональный трек «содержания»: расшифровка аудио и сравнение с текстом.

Требует Whisper (`pip install faster-whisper` или `openai-whisper`). Если он не
установлен, модуль просто недоступен — акустический анализ работает без него.

Сравнение расшифровки с исходным сценарием ловит пропущенные/лишние/перевранные
слова и даёт таймкод проблемного места.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class TranscriptIssue:
    start: float
    end: float
    kind: str        # missing / extra / substitution
    message: str
    detail: dict = field(default_factory=dict)


def transcribe(path: str, language: str = "ru", model: str = "large-v3") -> list[Word]:
    """Расшифровка с таймкодами по словам. Пробует faster-whisper, затем whisper."""
    try:
        from faster_whisper import WhisperModel

        m = WhisperModel(model, device="auto", compute_type="int8")
        segments, _ = m.transcribe(path, language=language, word_timestamps=True)
        words: list[Word] = []
        for seg in segments:
            for w in (seg.words or []):
                words.append(Word(w.word.strip(), float(w.start), float(w.end)))
        return words
    except ImportError:
        pass

    try:
        import whisper  # openai-whisper
    except ImportError as e:
        raise RuntimeError(
            "Для расшифровки установи один из пакетов: "
            "`pip install faster-whisper` (быстрее) или `pip install openai-whisper`."
        ) from e

    m = whisper.load_model(model)
    result = m.transcribe(path, language=language, word_timestamps=True)
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            words.append(Word(str(w["word"]).strip(), float(w["start"]), float(w["end"])))
    return words


def _norm(token: str) -> str:
    return re.sub(r"[^\wа-яё]", "", token.lower(), flags=re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t for t in (_norm(w) for w in re.findall(r"\S+", text)) if t]


def diff_against_script(words: list[Word], script: str) -> list[TranscriptIssue]:
    """Выравнивание расшифровки на исходный текст (Левенштейн по словам)."""
    from difflib import SequenceMatcher

    heard = [_norm(w.text) for w in words]
    heard_nonempty = [(i, t) for i, t in enumerate(heard) if t]
    heard_idx = [i for i, _ in heard_nonempty]
    heard_tokens = [t for _, t in heard_nonempty]
    script_tokens = _tokenize(script)

    sm = SequenceMatcher(a=script_tokens, b=heard_tokens, autojunk=False)
    issues: list[TranscriptIssue] = []

    def time_at(b_index: int) -> tuple[float, float]:
        if not heard_idx:
            return 0.0, 0.0
        b_index = max(0, min(b_index, len(heard_idx) - 1))
        w = words[heard_idx[b_index]]
        return w.start, w.end

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        s, e = time_at(j1 if j1 < len(heard_idx) else len(heard_idx) - 1)
        if tag == "delete":  # есть в тексте, нет в звуке → пропущено
            issues.append(TranscriptIssue(
                s, e, "missing",
                f"Пропущено при озвучке: «{' '.join(script_tokens[i1:i2])}»",
                {"script": script_tokens[i1:i2]},
            ))
        elif tag == "insert":  # есть в звуке, нет в тексте → лишнее
            _, e2 = time_at(j2 - 1)
            issues.append(TranscriptIssue(
                s, e2, "extra",
                f"Лишнее/повтор в озвучке: «{' '.join(heard_tokens[j1:j2])}»",
                {"heard": heard_tokens[j1:j2]},
            ))
        elif tag == "replace":  # прочитано иначе → возможна ошибка чтения/ударения
            _, e2 = time_at(j2 - 1)
            issues.append(TranscriptIssue(
                s, e2, "substitution",
                f"Прочитано иначе: в тексте «{' '.join(script_tokens[i1:i2])}», "
                f"слышно «{' '.join(heard_tokens[j1:j2])}»",
                {"script": script_tokens[i1:i2], "heard": heard_tokens[j1:j2]},
            ))
    return issues
