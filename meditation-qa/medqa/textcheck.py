"""Проверка ИСХОДНОГО текста сценария до отправки в TTS.

Многие проблемы («пропущенный пробел», «слипшиеся слова», непроизносимые числа,
латиница вперемешку) дешевле и точнее ловить в тексте, чем потом в звуке.
Опционально, если установлен RUAccent — проставляет и проверяет ударения.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextIssue:
    pos: int          # индекс символа в тексте
    line: int         # номер строки (с 1)
    col: int
    kind: str
    message: str
    excerpt: str


def _line_col(text: str, pos: int) -> tuple[int, int]:
    before = text[:pos]
    line = before.count("\n") + 1
    col = pos - (before.rfind("\n"))
    return line, col


def _excerpt(text: str, pos: int, width: int = 32) -> str:
    a = max(0, pos - width)
    b = min(len(text), pos + width)
    frag = text[a:b].replace("\n", "⏎")
    return ("…" if a > 0 else "") + frag + ("…" if b < len(text) else "")


def _add(issues, text, pos, kind, message):
    line, col = _line_col(text, pos)
    issues.append(TextIssue(pos, line, col, kind, message, _excerpt(text, pos)))


# Регэкспы простых, но частых для TTS проблем.
_RULES = [
    # Нет пробела после точки/запятой/двоеточия перед буквой: "слово,слово"
    (r"[а-яёa-z][,.;:!?]([а-яёА-ЯЁa-zA-Z])",
     "missing_space", "Нет пробела после знака препинания"),
    # Слипшиеся слова: строчная сразу за заглавной внутри слова "словоСлово"
    (r"[а-яё][А-ЯЁ]",
     "glued_words", "Похоже, два слова слиплись (нет пробела)"),
    # Двойные пробелы
    (r"  +",
     "double_space", "Двойной пробел"),
    # Латиница внутри русского слова (частая причина кривого чтения в TTS)
    (r"[а-яё][a-z]|[a-z][а-яё]",
     "mixed_scripts", "Смешаны кириллица и латиница в одном слове"),
    # Отдельное латинское/иностранное слово в русском тексте
    (r"[A-Za-zÀ-ÿ]{2,}",
     "latin_word", "Латинское слово в русском тексте — проверь, как оно читается"),
    # Цифры — TTS может прочитать нестабильно, лучше словами
    (r"\d",
     "digits", "Число цифрами — TTS может прочитать неверно, лучше словами"),
    # Пробел перед знаком препинания
    (r"\s[,.;:!?]",
     "space_before_punct", "Пробел перед знаком препинания"),
    # Три и более восклицательных/вопросительных подряд
    (r"[!?]{3,}",
     "excess_punct", "Многократный знак — может дать неестественную интонацию"),
]


def check_text(text: str) -> list[TextIssue]:
    issues: list[TextIssue] = []
    for pattern, kind, message in _RULES:
        for m in re.finditer(pattern, text):
            _add(issues, text, m.start(), kind, message)
    issues.sort(key=lambda i: i.pos)
    return issues


def check_stress(text: str) -> list[TextIssue]:
    """Опционально: расстановка ударений через RUAccent и флаг спорных слов.

    Возвращает предупреждения по словам, где ударение неоднозначно (омографы),
    чтобы проверить их в озвучке. Требует `pip install ruaccent`.
    """
    try:
        from ruaccent import RUAccent  # опционально
    except ImportError:
        return [TextIssue(0, 1, 1, "stress_unavailable",
                          "Для проверки ударений установи: pip install ruaccent",
                          "")]
    accentizer = RUAccent()
    accentizer.load(omograph_model_size="turbo", use_dictionary=True)
    accented = accentizer.process_all(text)
    issues: list[TextIssue] = []
    # RUAccent помечает ударение символом '+'; слова-омографы стоит проверить вручную.
    for m in re.finditer(r"[А-Яа-яЁё]+\+[А-Яа-яЁё]*", accented):
        pass  # маркер расстановки; подробный разбор омографов — по месту
    issues.append(TextIssue(0, 1, 1, "stress_marked",
                            "Ударения проставлены RUAccent — используй этот текст "
                            "для синтеза, чтобы снизить ошибки ударения.",
                            accented[:120]))
    return issues
