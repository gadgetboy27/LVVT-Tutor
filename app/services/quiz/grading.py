"""MCQ grading shared by the practice exam and the report card."""
import random
import re

_LETTERS = "ABCDEF"


def correct_index(question: dict) -> int:
    """Index of the correct option. correct_answer may be a letter ("B"), the full
    option text, or "B) text" — mirrors gradeMCQ in static/js/quiz.js."""
    options = question.get("options") or []
    ca = str(question.get("correct_answer") or "").strip()
    if not options or not ca:
        return -1
    for i, o in enumerate(options):
        if o.strip() == ca:
            return i
    if len(ca) == 1 and ca.upper() in _LETTERS[:len(options)]:
        return _LETTERS.index(ca.upper())
    for i, o in enumerate(options):
        if o.strip().lower().startswith(ca.lower() + ")"):
            return i
    low = ca.lower()
    for i, o in enumerate(options):
        if low in o.lower():
            return i
    return -1


def is_answer_correct(question: dict, user_answer: str) -> bool:
    """user_answer is the chosen option letter ("A".."F") or the option text."""
    idx = correct_index(question)
    if idx < 0 or not user_answer:
        return False
    ua = user_answer.strip()
    if len(ua) == 1 and ua.upper() in _LETTERS:
        return _LETTERS.index(ua.upper()) == idx
    options = question.get("options") or []
    return idx < len(options) and options[idx].strip().lower() == ua.lower()


_PREFIX = re.compile(r"^\s*[A-Fa-f][\).:]\s+")
_POSITIONAL = re.compile(r"\b(all|none) of the above\b|\bboth [A-D]\b|\b[A-D] and [A-D]\b", re.I)
# "Which document/chapter/form/rule contains X?" tests recall of where things are filed,
# not whether the applicant can apply the standard — poor closed-book questions.
_LOOKUP = re.compile(
    r"\b(which|what)\s+(other\s+)?(document|chapter|section|annex|form|manual|land transport rule|schedule)\b"
    r"|\bwhere\s+(are|is|does|do|can)\b[^?]{0,80}\b(found|contained|located|directed|specified|set out)\b"
    r"|\bmust (this|the) standard be read in conjunction\b",
    re.I,
)


def is_lookup_question(question: str) -> bool:
    return bool(_LOOKUP.search(question or ""))


def shuffle_question(q: dict) -> dict | None:
    """Randomise option order and relabel A-D, keeping the key correct.

    LLMs put the right answer first far too often (28 of 40 sampled questions were
    'A'), which lets a guesser score well. Returns None if the key can't be resolved,
    so a mis-keyed question is dropped rather than shipped. Questions whose options
    refer to each other ('all of the above') keep their order."""
    options = [_PREFIX.sub("", o).strip() for o in (q.get("options") or [])]
    idx = correct_index({"options": q.get("options"), "correct_answer": q.get("correct_answer")})
    if len(options) < 2 or idx < 0 or len(set(options)) != len(options):
        return None
    order = list(range(len(options)))
    if not any(_POSITIONAL.search(o) for o in options):
        random.shuffle(order)
    letters = "ABCDEF"
    labelled = [f"{letters[i]}) {options[j]}" for i, j in enumerate(order)]
    out = dict(q)
    out["options"] = labelled
    out["correct_answer"] = labelled[order.index(idx)]   # full option text, always among `options`
    return out


def prepare_questions(raw: list, n: int) -> list:
    """Shuffle, drop unresolvable keys, and prefer application questions over
    document-lookup ones (lookups are only kept to make up the numbers)."""
    shuffled = [s for s in (shuffle_question(q) for q in raw or []) if s]
    good = [q for q in shuffled if not is_lookup_question(q.get("question", ""))]
    lookups = [q for q in shuffled if is_lookup_question(q.get("question", ""))]
    return (good + lookups)[:n]
