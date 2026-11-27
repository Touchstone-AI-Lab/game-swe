"""Public-exam leakage gate for history tasks.

The starter and the reference *are* upstream code, so unlike the clean-room
gate this one only inspects the public exam: it must not hand the agent the
fix's identity (links, hashes, issue or pull-request numbers) or its own words
(the commit message, the pull-request text or a stretch of the diff).
"""

from __future__ import annotations

import re

from .models import HistoryFix

_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_HASH = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
_NUMBER = re.compile(r"(?<![\w&])#\d{1,6}\b")
_REFERENCE = re.compile(
    r"\b(?:pull request|merge request|fixing commit|upstream (?:fix|patch)|"
    r"the fix (?:changes|adds|replaces))\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9]+")
NGRAM = 8
PATCH_NGRAM = 12


def _grams(text: str, size: int) -> set[tuple[str, ...]]:
    words = _WORD.findall(text.casefold())
    return {tuple(words[index : index + size]) for index in range(len(words) - size + 1)}


def exam_leaks(exam: str, fix: HistoryFix) -> list[str]:
    findings: list[str] = []
    if _URL.search(exam):
        findings.append("the exam contains a URL")
    if _HASH.search(exam):
        findings.append("the exam contains a hexadecimal identifier that looks like a commit hash")
    if _NUMBER.search(exam):
        findings.append("the exam contains an issue or pull-request number")
    if _REFERENCE.search(exam):
        findings.append("the exam refers to the pull request or the upstream fix")
    prose = f"{fix.title}\n{fix.description}\n{fix.commit_message}"
    if _grams(exam, NGRAM) & _grams(prose, NGRAM):
        findings.append("the exam repeats the upstream pull-request or commit text")
    title_words = _WORD.findall(fix.title.casefold())
    if len(title_words) >= 5 and " ".join(title_words) in " ".join(_WORD.findall(exam.casefold())):
        findings.append("the exam repeats the upstream title")
    added = "\n".join(
        line[1:] for line in fix.patch.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    if _grams(exam, PATCH_NGRAM) & _grams(added, PATCH_NGRAM):
        findings.append("the exam quotes a stretch of the upstream diff")
    return findings
