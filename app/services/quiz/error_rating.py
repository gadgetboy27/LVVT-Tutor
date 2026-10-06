"""Hand-written, source-cited questions on how LVV Certifiers are actually assessed.

In practice a certifier's work is checked continuously through the LVV File Review
System, and any mistake is classed by the LVVTA Error Rating Table and converted to
points (LVV ORS Chapters 10 and 11). The application pathway is in Chapter 5. These
facts are exact and published, so the questions are deterministic rather than
AI-generated: no hallucinated rules, and they work with no AI key.

Every item below was written from the V13 chapter text; each explanation names its
section so the learner can check the source.
"""
import random
from typing import Dict, List

# (question, correct, distractors, explanation)
_CH11 = "ORS_Chapter_11"
_CH5 = "ORS_Chapter_5"

_BANK: Dict[str, List[tuple]] = {
    _CH11: [
        ("A certifier fails to submit a required LVV Inspection Form-set. Under the LVVTA Error Rating Table, how is this Error rated?",
         "Procedural", ["Technical Low", "Technical Medium", "Technical High"],
         "Table 11.1: a Procedural Error is where a required LVV Base Form or Inspection Form-set was not submitted, or a modification was not identified (ORS Ch.11, 2.3)."),
        ("A certifier certifies a vehicle where a critical safety-related requirement was not met and the fault could cause sudden, complete failure and a loss of braking or directional control. How is this Error rated?",
         "Technical High", ["Technical Medium", "Technical Low", "Procedural"],
         "Table 11.1: Technical High is a critical safety-related requirement not met that may cause sudden and complete failure with loss of directional or braking control (ORS Ch.11, 2.3)."),
        ("A technical requirement was not met, but it is unlikely to cause an accident or make the outcome of an accident worse. How is the Error rated?",
         "Technical Low", ["Technical Medium", "Technical High", "Procedural"],
         "Table 11.1: Technical Low means the requirement was not met but is unlikely to cause or worsen an accident (ORS Ch.11, 2.3)."),
        ("A safety-related requirement was not met. It is unlikely to cause a sudden, complete failure, but over time, fatigue or loading it could contribute to a failure. How is the Error rated?",
         "Technical Medium", ["Technical Low", "Technical High", "Procedural"],
         "Table 11.1: Technical Medium covers requirements that may worsen an accident, or safety-related requirements that need time, circumstances, fatigue or loading to cause failure (ORS Ch.11, 2.3)."),
        ("A certifier failed to identify a modification, and not identifying it creates a risk to vehicle safety. What can happen to the Procedural Error?",
         "It can be escalated to a Technical Low, Medium or High Error depending on the safety risk",
         ["Nothing — it stays Procedural because paperwork is not a safety matter",
          "It is always escalated to Technical High",
          "It is cancelled if the certifier corrects the form"],
         "Table 11.1 Note 1: a Procedural Error for failing to identify a modification may be escalated to Low, Medium or High Technical if there is a risk to vehicle safety (ORS Ch.11, 2.3)."),
        ("The same Procedural Error keeps being made by a certifier despite coaching from LVVTA. What may happen?",
         "It may be escalated to a Technical Low Error",
         ["It is ignored because Procedural Errors do not count", "It becomes a Technical High Error", "The certifier is automatically suspended"],
         "Table 11.1 Note 2: a repeated Procedural Error despite coaching may be escalated to Technical Low (ORS Ch.11, 2.3)."),
        ("In the Error Report points system, how many Procedural Errors equal one point?",
         "Eight", ["One", "Two", "Four"],
         "ORS Ch.11, 3.3(2): eight Procedural = one point; four Technical Low = one; two Technical Medium = one; one Technical High = one."),
        ("In the Error Report points system, how many Technical Medium Errors equal one point?",
         "Two", ["One", "Four", "Eight"],
         "ORS Ch.11, 3.3(2): two Technical Medium Errors equal one point."),
        ("In the Error Report points system, a single Technical High Error is worth how many points?",
         "One point on its own", ["One quarter of a point", "Half a point", "Four points"],
         "ORS Ch.11, 3.3(2): one Technical High Error equals one point — the same as eight Procedural Errors."),
        ("Error points recorded against a certifier are divided by what, so that busy and quiet certifiers can be compared fairly?",
         "The number of certifications completed over the preceding 12 months",
         ["The number of years the certifier has held appointment", "The number of Errors made by all certifiers", "The certifier's total number of inspection forms"],
         "ORS Ch.11, 3.3(2) Note 1: points are divided by the certifications completed in the preceding 12-month period."),
        ("After LVVTA notifies a certifier of an assigned Error, how long should the certifier take to respond with clarification or to dispute the Error type?",
         "Five working days", ["Twenty-four hours", "Ten working days", "Thirty days"],
         "ORS Ch.11, 2.4 Note 5: the certifier should respond within five working days from the date the Error is communicated."),
        ("Who jointly agrees each Error type and assigns the Error to the certifier?",
         "LVVTA and NZTA, at the LVVTA-NZTA Technical Working Group meeting",
         ["LVVTA staff alone, privately", "The certifier's regional peer group", "NZTA alone, by audit"],
         "ORS Ch.11, 2.4(1)(b): Errors are discussed at the LVVTA-NZTA Technical Working Group, which jointly agrees the Error type so the process is fair and transparent."),
        ("An Error is identified as a safety risk with an 'extreme' risk rating. What must LVVTA do?",
         "Refer it to NZTA as a formal complaint", ["Record it as a Procedural Error only", "Wait for the annual summary before acting", "Leave it to the certifier to resolve"],
         "ORS Ch.11, 2.4(1)(e) and Note 6: LVVTA is required by its agreement with NZTA to refer 'extreme' safety risks to NZTA as a formal complaint."),
    ],
    _CH5: [
        ("What is the minimum pass mark for the Pre-assessment Technical Competence Test for an LVV Certifier applicant?",
         "No less than 80%", ["No less than 60%", "No less than 70%", "No less than 90%"],
         "ORS Ch.5, Section 6, Note 2: the required pass mark must be no less than 80%."),
        ("The written part of the LVV Certifier Formal Assessment is a closed-book multiple-choice test. What are its length, time limit and pass requirement?",
         "20 questions in 30 minutes; at least 15 correct", ["10 questions in 15 minutes; at least 8 correct", "30 questions in 60 minutes; at least 24 correct", "20 questions in 60 minutes; at least 18 correct"],
         "ORS Ch.5, 10.3(2)(a): a written multi-choice closed book test of 20 questions in 30 minutes, with a pass rate of not less than 15 correct answers."),
        ("Who must be present to conduct the LVV Certifier Formal Assessment?",
         "At least one representative each from NZTA and LVVTA", ["An LVVTA representative only", "A senior certifier from the applicant's region", "Two LVVTA representatives and no NZTA staff"],
         "ORS Ch.5, 10.3(2): conducted by not less than one representative each from NZTA and LVVTA."),
        ("Which stage immediately follows an applicant passing the Formal Assessment?",
         "Induction Training", ["Appointment as an LVV Certifier", "Pre-assessment", "The File Review probationary period"],
         "ORS Ch.5, 2.3: pass the Formal Assessment, then Induction Training, then Pre-appointment Mentoring, then NZTA appoints the applicant."),
        ("Where does the Pre-assessment take place?",
         "At the applicant's own premises", ["At the LVVTA office in Porirua", "At an NZTA testing station", "Online"],
         "ORS Ch.5, 6.2(1): the Pre-assessment takes place at the applicant's premises (a home garage can qualify); the Formal Assessment is at LVVTA's premises."),
    ],
}


def _build(q: str, correct: str, wrong: List[str], explanation: str) -> dict:
    options = [correct] + list(wrong)
    random.shuffle(options)
    letters = "ABCD"
    labelled = [f"{letters[i]}) {o}" for i, o in enumerate(options)]
    return {
        "question": q,
        "options": labelled,
        # Full option text (not a bare letter) so it is always among `options`.
        "correct_answer": labelled[options.index(correct)],
        "explanation": explanation,
        "difficulty": "medium",
        "type": "MCQ",
    }


def curated_questions(standard_number: str, n: int) -> List[dict]:
    """Up to n cited questions for this standard (random order, shuffled options)."""
    bank = _BANK.get(standard_number) or []
    picked = random.sample(bank, min(n, len(bank)))
    return [_build(*item) for item in picked]
