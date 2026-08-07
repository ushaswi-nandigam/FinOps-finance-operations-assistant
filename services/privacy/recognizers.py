"""Regex-based Indian PII recognisers.

architecture.md's original design calls for Presidio + spaCy extended with
Indian recognisers. This project uses only the Indian-recognisers half: for
a fixed, well-known set of formats (PAN, Aadhaar, card, UPI, IFSC, phone,
email) a validated regex is exactly as correct as Presidio's recognisers
would be (Presidio's Indian support *is* regex + checksum under the hood),
without the spaCy model download. See docs/LEARN.md for the full trade-off.
"""

import re
from dataclasses import dataclass
from typing import Callable

PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
EMAIL_RE = re.compile(r"\b[\w.\-]+@[\w\-]+\.[a-zA-Z]{2,}\b")
UPI_RE = re.compile(r"\b[\w.\-]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,64}\b")
AADHAAR_RE = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
PHONE_RE = re.compile(r"(?:\+91[\-\s]?)?\b[6-9]\d{9}\b")

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_checksum_valid(digits: str) -> bool:
    """Standard Verhoeff algorithm — used by Aadhaar for its check digit."""
    if not digits.isdigit() or len(digits) != 12:
        return False
    c = 0
    for i, digit in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return c == 0


def luhn_valid(digits: str) -> bool:
    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return False
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


@dataclass
class Match:
    start: int
    end: int
    label: str
    value: str
    priority: int


def _strip(s: str) -> str:
    return re.sub(r"[ \-]", "", s)


def _find(pattern: re.Pattern, label: str, priority: int, text: str,
          validator: Callable[[str], bool] | None = None) -> list[Match]:
    matches = []
    for m in pattern.finditer(text):
        value = m.group(0)
        if validator and not validator(_strip(value)):
            continue
        matches.append(Match(m.start(), m.end(), label, value, priority))
    return matches


def find_pii(text: str) -> list[Match]:
    """Finds every recognised PII span, priority order breaking overlap ties
    (lower number wins). Non-overlapping matches are all kept."""
    candidates: list[Match] = []
    candidates += _find(PAN_RE, "PAN", 0, text)
    candidates += _find(IFSC_RE, "IFSC", 1, text)
    candidates += _find(EMAIL_RE, "EMAIL", 2, text)
    candidates += _find(AADHAAR_RE, "AADHAAR", 3, text, validator=verhoeff_checksum_valid)
    candidates += _find(CARD_RE, "CARD", 4, text, validator=luhn_valid)
    candidates += _find(UPI_RE, "UPI", 5, text)
    candidates += _find(PHONE_RE, "PHONE", 6, text)

    candidates.sort(key=lambda m: (m.start, m.priority, -(m.end - m.start)))
    selected: list[Match] = []
    last_end = -1
    for m in candidates:
        if m.start >= last_end:
            selected.append(m)
            last_end = m.end
    return selected
