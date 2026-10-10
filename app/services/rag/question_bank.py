"""Pre-generate an exam-style question bank from the verified study-guide passages.

Two safeguards beyond the study guide's own quote verification:
  1. Every question is written from ONE verified passage, so it has a source quote and page.
  2. An independent second pass is shown only the quote, the question and the options (never
     the answer key) and must choose the same answer; questions where it disagrees, or where
     the passage can't answer the question, are discarded.
"""
import json
import math
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List

from app.services.quiz.grading import correct_index, is_lookup_question, shuffle_question

BATCH_POINTS = 8
MAX_QUESTIONS_PER_STANDARD = 60
VERIFY_BATCH = 10

GEN_SYSTEM = """You write multiple-choice questions for the LVV (Low Volume Vehicle) Certifier written test in New Zealand.
The test is closed-book and checks whether a person can APPLY the standards and procedures to real vehicles safely."""


def _gen_prompt(batch: List[dict], title: str, n: int) -> str:
    passages = "\n\n".join(f'[P{i}] (page {p["page"]}{", clause " + p["section"] if p.get("section") else ""})\n'
                           f'Quote: {p["quote"]}\nIn short: {p["point"]}' for i, p in enumerate(batch, 1))
    return f"""Document: "{title}"

Write {n} multiple-choice questions, each based on exactly ONE of the passages below.

Rules:
- Roughly half should be short SCENARIOS ("A certifier inspects a vehicle where ... What must they do?"); the rest test a specific requirement applied to a concrete case.
- The correct answer must follow from the passage's quote ALONE. Do not rely on outside knowledge and never invent figures.
- The question must NOT state or paraphrase its own answer. The correct option has to add the rule, consequence or action that the question leaves out. If the question already describes the fault ("the fasteners crush the tube"), do not make "the fasteners crush the tube" the answer.
- Do not ask for a term when the question already contains its definition.
- Only test things a certifier applies when inspecting, deciding or following procedure. Skip glossary entries, acronyms and LVVTA's own internal reporting formats.
- Do NOT ask which document, chapter, section or form contains something.
- Four options, one clearly correct; the wrong ones are plausible mistakes a real applicant might make. Keep all options similar in length and detail; the correct one must not be the longest. No "all/none of the above".
- Refer to the document by its plain name, never by a file-style identifier.
- "explanation": one or two sentences saying why the answer is right, citing the clause if given.

Return a JSON array only:
[{{"passage": <number after P>, "question": "...", "options": ["A) ...","B) ...","C) ...","D) ..."], "correct_answer": "A", "explanation": "..."}}]

PASSAGES:
{passages}"""


def _verify_prompt(items: List[dict]) -> str:
    blocks = "\n\n".join(f'[{i}] Passage: {it["quote"]}\nQuestion: {it["question"]}\nOptions: ' + " | ".join(it["options"])
                         for i, it in enumerate(items, 1))
    return f"""For each item, use ONLY its passage to decide which option is correct. If the passage does not let you decide, answer "?".
Return a JSON object mapping each item number to a single letter, e.g. {{"1": "B", "2": "?"}}. Nothing else.

{blocks}"""


def _judge_prompt(items: List[dict]) -> str:
    blocks = "\n\n".join(f'[{i}] Question: {it["question"]}\nCorrect answer: {it["answer"]}' for i, it in enumerate(items, 1))
    return f"""You review exam questions for the LVV Certifier written test. For each item answer two things:
- "restates": true if the correct answer mostly repeats or paraphrases information ALREADY STATED IN THE QUESTION itself, so a reader could answer without knowing the standard.
- "relevant": true only if a working certifier needs this to apply the standards or follow procedure; false for glossary entries, acronyms, trivia, or LVVTA's internal reporting formats.
Return a JSON object like {{"1": {{"restates": false, "relevant": true}}, "2": {{"restates": true, "relevant": true}}}}. Nothing else.

{blocks}"""


def judge_questions(questions: List[dict], llm: Callable[[str, str, int], str], workers: int = 4) -> List[dict]:
    """Return one verdict dict per question: {'restates': bool, 'relevant': bool}. A question whose
    judgement is missing or malformed gets restates=True (rejected): unchecked never passes."""
    groups = [questions[i:i + VERIFY_BATCH] for i in range(0, len(questions), VERIFY_BATCH)]

    def run(group):
        try:
            data = _json_object(llm("You review exam questions.", _judge_prompt(
                [{"question": q["question"], "answer": q["correct_answer"]} for q in group]), 800))
        except Exception as e:
            print(f"question bank: judging failed: {e}")
            data = {}
        out = []
        for i in range(1, len(group) + 1):
            v = data.get(str(i)) if isinstance(data, dict) else None
            if isinstance(v, dict) and isinstance(v.get("restates"), bool) and isinstance(v.get("relevant"), bool):
                out.append(v)
            else:
                out.append({"restates": True, "relevant": False})
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = [v for group in pool.map(run, groups) for v in group]
    return verdicts


def _json_array(raw: str) -> List[dict]:
    s, e = raw.find("["), raw.rfind("]") + 1
    try:
        return [d for d in json.loads(raw[s:e]) if isinstance(d, dict)] if s != -1 and e > s else []
    except json.JSONDecodeError:
        return []


def _json_object(raw: str) -> Dict:
    s, e = raw.find("{"), raw.rfind("}") + 1
    try:
        return json.loads(raw[s:e]) if s != -1 and e > s else {}
    except json.JSONDecodeError:
        return {}


def build_questions(points: List[dict], title: str, llm: Callable[[str, str, int], str],
                    workers: int = 4) -> Dict:
    """points: study-guide dicts (page, quote, point, section, importance). Returns verified questions + stats."""
    ranked = sorted(points, key=lambda p: (p["importance"], p["page"]))
    cap = MAX_QUESTIONS_PER_STANDARD
    chosen = sorted(ranked[:math.ceil(cap / 0.7)], key=lambda p: p["page"])
    batches = [chosen[i:i + BATCH_POINTS] for i in range(0, len(chosen), BATCH_POINTS)]

    def gen(batch):
        n = max(2, round(len(batch) * 0.7))
        try:
            return batch, _json_array(llm(GEN_SYSTEM, _gen_prompt(batch, title, n), 4000))
        except Exception as e:
            print(f"question bank: generation failed: {e}")
            return batch, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        generated = list(pool.map(gen, batches))

    candidates, failed, seen, dropped_format = [], 0, set(), 0
    for batch, items in generated:
        if items is None:
            failed += 1
            continue
        for it in items:
            idx = it.get("passage")
            if not isinstance(idx, int) or not 1 <= idx <= len(batch):
                dropped_format += 1
                continue
            src = batch[idx - 1]
            q = shuffle_question({"question": str(it.get("question") or "").strip(), "options": it.get("options"),
                                  "correct_answer": it.get("correct_answer"),
                                  "explanation": str(it.get("explanation") or "").strip()})
            if (not q or not q["question"] or not q["explanation"] or len(q["options"]) != 4
                    or is_lookup_question(q["question"]) or q["question"].lower() in seen):
                dropped_format += 1
                continue
            seen.add(q["question"].lower())
            q.update(source_page=src["page"], source_quote=src["quote"], source_section=src.get("section") or "")
            candidates.append(q)

    # Independent answerability check: the verifier never sees the key.
    groups = [candidates[i:i + VERIFY_BATCH] for i in range(0, len(candidates), VERIFY_BATCH)]

    def verify(group):
        try:
            answers = _json_object(llm("You check exam questions against a source passage.",
                                       _verify_prompt([{"quote": g["source_quote"], "question": g["question"],
                                                        "options": g["options"]} for g in group]), 600))
        except Exception as e:
            print(f"question bank: verification failed: {e}")
            return group, None
        return group, answers

    with ThreadPoolExecutor(max_workers=workers) as pool:
        checked = list(pool.map(verify, groups))

    kept, rejected, unchecked = [], 0, 0
    answerable = []
    for group, answers in checked:
        if answers is None:
            unchecked += len(group)          # a failed check never lets a question through
            continue
        for i, q in enumerate(group, 1):
            letter = str(answers.get(str(i), "?")).strip().upper()[:1]
            if letter == "ABCD"[correct_index(q)]:
                answerable.append(q)
            else:
                rejected += 1

    # Answerable from the quote is not enough: a question can be answerable because its stem
    # gives the answer away, or can test glossary trivia. Judge both.
    leaked = irrelevant = 0
    for q, v in zip(answerable, judge_questions(answerable, llm, workers)):
        if v["restates"]:
            leaked += 1
        elif not v["relevant"]:
            irrelevant += 1
        else:
            kept.append(q)
    random.shuffle(kept)
    kept = kept[:MAX_QUESTIONS_PER_STANDARD]
    return {"questions": kept,
            "stats": {"passages": len(chosen), "batches": len(batches), "failed_batches": failed,
                      "candidates": len(candidates), "dropped_format": dropped_format,
                      "rejected_by_check": rejected, "restating": leaked, "irrelevant": irrelevant,
                      "unchecked": unchecked, "kept": len(kept)}}


# --------------------------------------------------------------------------- persistence / serving
_FIELDS = ("question", "options", "correct_answer", "explanation", "difficulty",
           "source_page", "source_quote", "source_section", "source_hash")


def replace_bank(db, standard_id: int, questions: List[dict], source_hash: str = None) -> int:
    from app.models.bank import BankQuestion
    db.query(BankQuestion).filter(BankQuestion.standard_id == standard_id).delete()
    for q in questions:
        db.add(BankQuestion(standard_id=standard_id, source_hash=source_hash, difficulty="medium",
                            **{k: q[k] for k in ("question", "options", "correct_answer", "explanation",
                                                 "source_page", "source_quote", "source_section")}))
    db.commit()
    return len(questions)


def sample_questions(db, standard_id: int, n: int) -> List[dict]:
    """Up to n random bank questions in the QuizQuestion shape, with the source page appended."""
    from app.models.bank import BankQuestion
    rows = db.query(BankQuestion).filter(BankQuestion.standard_id == standard_id).all()
    random.shuffle(rows)
    return [_as_quiz(r) for r in rows[:n]]


def _as_quiz(r) -> dict:
    page = f" (Official document, page {r.source_page}.)" if r.source_page else ""
    return {"question": r.question, "options": list(r.options), "correct_answer": r.correct_answer,
            "explanation": r.explanation + page, "difficulty": r.difficulty or "medium", "type": "MCQ"}


def bank_size(db, standard_id: int) -> int:
    from app.models.bank import BankQuestion
    return db.query(BankQuestion).filter(BankQuestion.standard_id == standard_id).count()


def export_bank(db, path: str) -> int:
    import gzip
    from app.models.bank import BankQuestion
    from app.models.quiz import Standard
    numbers = {s.id: s.standard_number for s in db.query(Standard).all()}
    rows = [{"standard_number": numbers[r.standard_id], **{k: getattr(r, k) for k in _FIELDS}}
            for r in db.query(BankQuestion).order_by(BankQuestion.standard_id, BankQuestion.id).all()
            if r.standard_id in numbers]
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(rows, f)
    return len(rows)


def _fingerprint(texts) -> str:
    import hashlib
    return hashlib.sha1("\n".join(sorted(texts)).encode()).hexdigest()


def load_bank(db, path: str) -> Dict:
    """Make each standard's stored bank match the shipped file. Standards without questions get them;
    a standard whose questions differ (e.g. flawed ones were removed) is replaced. Idempotent."""
    import gzip
    import os
    from collections import defaultdict
    from app.models.bank import BankQuestion
    from app.models.quiz import Standard
    if not os.path.exists(path):
        return {"skipped": f"{path} not found"}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    ids = {s.standard_number: s.id for s in db.query(Standard).all()}
    shipped = defaultdict(list)
    for r in rows:
        if r["standard_number"] in ids:
            shipped[r["standard_number"]].append(r)
    stored = defaultdict(list)
    for bq in db.query(BankQuestion).all():
        stored[bq.standard_id].append(bq)

    added = replaced = 0
    for number, items in shipped.items():
        sid = ids[number]
        if _fingerprint(i["question"] for i in items) == _fingerprint(b.question for b in stored.get(sid, [])):
            continue
        if stored.get(sid):
            db.query(BankQuestion).filter(BankQuestion.standard_id == sid).delete()
            replaced += 1
        for r in items:
            db.add(BankQuestion(standard_id=sid, **{k: r[k] for k in _FIELDS}))
            added += 1
    db.commit()
    return {"added": added, "standards": len(shipped), "replaced": replaced}
