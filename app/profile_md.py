"""Parse/serialise the user portrait MD file (sectioned by question key)."""

from __future__ import annotations

import re

from app.questions import ONBOARDING_QUESTIONS, OnboardingQuestion

PROFILE_TITLE: str = "# Портрет автора"
_MARKER_RE: re.Pattern[str] = re.compile(r"<!--\s*200b:section=([A-Za-z0-9_\-]+)\s*-->")


def _section_marker(key: str) -> str:
    return f"<!-- 200b:section={key} -->"


def parse_sections(md: str) -> dict[str, str]:
    """Извлекает {section_key -> answer_text} из MD по маркерам."""
    result: dict[str, str] = {}
    parts: list[str] = _MARKER_RE.split(md)
    # parts = [preamble, key1, body1, key2, body2, ...]
    for i in range(1, len(parts), 2):
        key: str = parts[i]
        body: str = parts[i + 1] if i + 1 < len(parts) else ""
        # Body: optional "## <question text>" line, then the answer
        lines: list[str] = body.lstrip("\n").split("\n")
        if lines and lines[0].startswith("## "):
            lines = lines[1:]
        answer: str = "\n".join(lines).strip()
        result[key] = answer
    return result


def serialize_sections(answers: dict[str, str]) -> str:
    """Собирает канонический MD из {key -> answer}, используя порядок ONBOARDING_QUESTIONS."""
    out: list[str] = [PROFILE_TITLE, ""]
    for q in ONBOARDING_QUESTIONS:
        if q.key not in answers:
            continue
        out.append(_section_marker(q.key))
        out.append(f"## {q.text}")
        out.append("")
        out.append(answers[q.key].strip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def upsert_answer(md: str, *, key: str, answer_text: str) -> str:
    existing: dict[str, str] = parse_sections(md)
    existing[key] = answer_text.strip()
    return serialize_sections(existing)


def first_unanswered(md: str) -> OnboardingQuestion | None:
    answered: set[str] = {k for k, v in parse_sections(md).items() if v}
    for q in ONBOARDING_QUESTIONS:
        if q.key not in answered:
            return q
    return None


def answered_count(md: str) -> int:
    return sum(1 for v in parse_sections(md).values() if v)
