"""Finds @mentions in a Markdown message and rewrites them to "@<participant id>".

Rewriting to the id means a mention keeps pointing at the right participant even if
they rename later, and the frontend can always show their current name.
"""

import re
from dataclasses import dataclass

# Text where an "@" never starts a mention: code blocks, inline code, and links.
PROTECTED_TEXT_PATTERN = re.compile(r"```.*?(```|$)|`[^`\n]*`|https?://\S+", re.DOTALL)
# An "@" right after a letter, digit, or backslash is not a mention (emails, escaped "\@").
MENTION_START_PATTERN = re.compile(r"(?<![\w\\])@")


@dataclass(frozen=True)
class MentionCandidate:
    participant_id: str
    display_name: str


def resolve_mentions(body: str, candidates: list[MentionCandidate]) -> tuple[str, list[str]]:
    """Return the body with mentions rewritten to ids, and the mentioned ids in order.

    "@<id>" always wins. Otherwise "@<display name>" matches in any letter case, as long as
    exactly one candidate has that name. The longest match wins, so "@Ann Lee" beats "@Ann".
    """
    ids_longest_first = sorted((c.participant_id for c in candidates), key=len, reverse=True)
    names_longest_first = _unambiguous_names_longest_first(candidates)
    protected_ranges = [match.span() for match in PROTECTED_TEXT_PATTERN.finditer(body)]

    rewritten_parts: list[str] = []
    mentioned_ids: list[str] = []
    copied_up_to = 0
    for match in MENTION_START_PATTERN.finditer(body):
        at_position = match.start()
        if at_position < copied_up_to or _is_inside(at_position, protected_ranges):
            continue
        text_after_at = body[at_position + 1 :]
        found = _match_id(text_after_at, ids_longest_first) or _match_name(
            text_after_at, names_longest_first
        )
        if found is None:
            continue
        participant_id, matched_length = found
        rewritten_parts.append(body[copied_up_to:at_position])
        rewritten_parts.append(f"@{participant_id}")
        copied_up_to = at_position + 1 + matched_length
        if participant_id not in mentioned_ids:
            mentioned_ids.append(participant_id)

    rewritten_parts.append(body[copied_up_to:])
    return "".join(rewritten_parts), mentioned_ids


def _unambiguous_names_longest_first(candidates: list[MentionCandidate]) -> list[tuple[str, str]]:
    ids_by_lowercase_name: dict[str, set[str]] = {}
    for candidate in candidates:
        ids_by_lowercase_name.setdefault(candidate.display_name.lower(), set()).add(
            candidate.participant_id
        )
    unambiguous = [
        (name, next(iter(ids))) for name, ids in ids_by_lowercase_name.items() if len(ids) == 1
    ]
    return sorted(unambiguous, key=lambda name_and_id: len(name_and_id[0]), reverse=True)


def _match_id(text_after_at: str, ids_longest_first: list[str]) -> tuple[str, int] | None:
    for participant_id in ids_longest_first:
        if text_after_at.startswith(participant_id) and _ends_cleanly(
            text_after_at, len(participant_id)
        ):
            return participant_id, len(participant_id)
    return None


def _match_name(
    text_after_at: str, names_longest_first: list[tuple[str, str]]
) -> tuple[str, int] | None:
    lowercase_text = text_after_at.lower()
    for lowercase_name, participant_id in names_longest_first:
        if lowercase_text.startswith(lowercase_name) and _ends_cleanly(
            text_after_at, len(lowercase_name)
        ):
            return participant_id, len(lowercase_name)
    return None


def _ends_cleanly(text: str, match_length: int) -> bool:
    """True when the match is not just the start of a longer word ("@Ann" inside "@Anna")."""
    if match_length >= len(text):
        return True
    next_character = text[match_length]
    return not (next_character.isalnum() or next_character in "-_")


def _is_inside(position: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in ranges)
