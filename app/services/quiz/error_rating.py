"""Hand-written, source-cited questions on what LVV Certifiers are actually held to.

In practice a certifier's work is checked continuously through the LVV File Review
System, and any mistake is classed by the LVVTA Error Rating Table and converted to
points (ORS Ch.10 and 11). The application pathway and background criteria are in
Ch.5 and Ch.4; conduct, independence and conflict of interest in Ch.7; and the
inspection procedure itself (what the practical assessment is about) in Ch.8. These
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
_CH4 = "ORS_Chapter_4"
_CH7 = "ORS_Chapter_7"
_CH8 = "ORS_Chapter_8"

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

_BANK[_CH5].extend([
        ("Besides the background criteria and personal attributes, what must an appointed LVV Certifier also establish or obtain?",
         "A quality management system, and public liability and professional indemnity insurance",
         ["A workshop of at least a set floor area, and a vehicle hoist", "A second certifier as a permanent partner", "A fixed annual sum held in trust by LVVTA"],
         "ORS Ch.5, 3.4(1): establish a quality management system (which may be the NZTA Performance Review System) and maintain public liability and professional indemnity insurance."),
        ("The character part of the Formal Assessment looks at whether an applicant is likely to do what?",
         "Work with NZTA and LVVTA in a spirit of co-operation, including the File Review System, and put vehicle safety first",
         ["Compete with other certifiers for the largest share of work", "Work entirely alone, without feedback from LVVTA", "Prioritise customer turnaround time above other considerations"],
         "ORS Ch.5, 10.3(2)(d): evaluates willingness to work within the team environment with LVVTA and the certifiers, particularly the File Review System, and to place motor vehicle safety as the highest priority."),
        ("What does the Pre-assessment let LVVTA do with the applicant's own work?",
         "Inspect vehicles the applicant owns, built or modified, and discuss the work in depth",
         ["Review only the applicant's written CV", "Observe the applicant certifying a customer's vehicle", "Re-test the applicant on the PowerPoint examination"],
         "ORS Ch.5, 6.2(2)(b): a senior LVVTA technical representative inspects vehicles the applicant owns or has modified or built and confirms knowledge and experience through in-depth discussion."),
])

_BANK[_CH4] = [
    ("According to ORS Chapter 4, what does being a motor mechanic or engineer alone provide?",
     "A good platform, but not enough on its own for the safety judgements LVV certification needs",
     ["Full qualification to certify any category", "Nothing — such trades are excluded from appointment", "Automatic appointment to LV1A"],
     "ORS Ch.4, 1.2: being a motor mechanic or engineer is a good platform but not enough; the knowledge comes from extensive practical involvement in vehicle modification and construction."),
    ("Which of these is one of the ways ORS Chapter 4 allows an applicant to show industry-expert experience for category LV1A?",
     "Two years' full-time practical experience in vehicle modification work with significant complexity and wide-ranging diversity",
     ["Holding a mechanical trade certificate and no modification work", "Six months' experience doing WoF inspections", "A letter of support from a vehicle owner"],
     "ORS Ch.4, 2.2(1)(b): two years' full-time modification experience, or a variety of complex (primarily mechanical) modifications, or equivalent experience judged entirely relevant."),
    ("Where is it determined whether an applicant meets the knowledge and experience criteria for a category?",
     "At the LVV Certifier Pre-assessment", ["On submitting the written application form", "At the final induction training", "During the first year's File Review"],
     "ORS Ch.4, 2.2(1)(b) Note 1: the Pre-assessment in ORS Chapter 5 determines whether the knowledge and experience criteria are met."),
    ("Does an applicant have to be working in the motor industry at the time they apply?",
     "No — the experience can have been built up over a career", ["Yes, they must be currently employed in it", "Yes, but only in a vehicle manufacturer", "Only if applying for LV1D"],
     "ORS Ch.4, 1.5 Note 1: the high level of knowledge and experience can be accumulated over a career; the applicant need not be engaged in the industry when applying."),
    ("Ideally, a new LVV Certifier starts at which category and works upward?",
     "LV1A", ["LV1D", "LV2B", "LV4"],
     "ORS Ch.4, 1.4: the objective is, wherever possible, to start a new LVV Certifier with category LV1A and work upwards."),
    ("Why does ORS Chapter 4 say LVV certification needs people with practical modification experience?",
     "If a certifier cannot tell that a modification has occurred, they cannot ensure it was done safely",
     ["Because LVVTA cannot afford to train people", "Because modification work is always low-risk", "Because NZTA requires a trade qualification"],
     "ORS Ch.4, 1.2: if a certifier is unable to determine that modifications have occurred in the first place, there is no chance of ensuring they were carried out correctly and safely."),
]

_BANK[_CH7] = [
    ("A vehicle was modified by a mechanic employed by the certifier's own workshop. May that certifier certify it?",
     "No — a professional conflict of interest exists", ["Yes, if the mechanic is qualified", "Yes, if a second certifier countersigns the forms", "Yes, if the owner agrees in writing"],
     "ORS Ch.7, 2.3(1)(b)(iii) and Note 3: a certifier cannot certify a vehicle modified or built by a staff member, contractor or business they own."),
    ("A certifier's close family member part-owns a vehicle presented for certification. What applies?",
     "The certifier must not certify it — a financial interest exists", ["It is acceptable if the share is under half", "It is acceptable if disclosed on the forms", "Only the family member's share must be re-inspected"],
     "ORS Ch.7, 2.3(1)(a) and Note 1: financial interest includes partial ownership by the certifier or a close family member."),
    ("A customer is also the certifier's employer. May the certifier certify the customer's vehicle?",
     "No — the certifier's customer cannot also be their employer", ["Yes, because the work was done by someone else", "Yes, if the fee is waived", "Yes, if the vehicle is scratch-built"],
     "ORS Ch.7, 2.3(1)(b)(ii) and Note 2: a certifier cannot be in a position where the customer is also the certifier's employer."),
    ("May a certifier give a customer advice on how to fix a problem found during an inspection?",
     "Yes, provided the certifier does not carry out the modifications themselves (beyond remedial work allowed by ORS Chapter 8)",
     ["No — any advice creates a conflict of interest", "Yes, and they may then carry out the work and certify it", "Only if NZTA approves the advice in advance"],
     "ORS Ch.7, 2.3 Note 4: the conflict rule is not intended to stop a certifier giving advice or solutions, provided they have not carried out the modifications."),
    ("Which is a valid reason for a certifier to refuse to inspect a low volume vehicle?",
     "They do not hold the certification category the vehicle or modification needs",
     ["The job would not be very profitable", "The owner complained about them previously", "The certifier is busy this month"],
     "ORS Ch.7, 3.3(1): a certifier must not refuse unless they lack the category, would be outside their area of expertise, or believe their personal safety may be compromised."),
    ("A certifier declines a vehicle because it is outside their area of expertise. What must they do?",
     "Refer the owner to an appropriately experienced and authorised LVV Certifier", ["Certify it provisionally and review later", "Return the vehicle with no further comment", "Ask the owner to find an engineer's report instead"],
     "ORS Ch.7, 3.3(1) Note 1: where the category or expertise reason applies, the certifier must refer the owner to an appropriately experienced and authorised certifier."),
    ("A certifier will be unavailable for an extended period, such as a holiday. What are they required to do?",
     "Provide contact details for an alternative LVV Certifier", ["Close their calendar and pause all enquiries", "Hand their certification files to the customer", "Ask LVVTA to answer enquiries on their behalf"],
     "ORS Ch.7, 3.2(1)(d): provide contact details for an alternative LVV Certifier available to anyone needing LVV certification during that time."),
    ("In what capacity do LVV Certifiers operate?",
     "As appointed agents of the NZ Transport Agency, in a professional capacity", ["As employees of LVVTA", "As independent traders with no regulatory role", "As volunteers of the vehicle clubs"],
     "ORS Ch.7, 1.1 and 2.1: LVV Certifiers are appointed agents of NZTA, operating in a professional capacity and expected to maintain complete independence."),
]

_BANK[_CH8] = [
    ("During an inspection a certifier finds a modification outside the categories they hold. What must they do?",
     "Refer the owner to a certifier who holds the right category, or apply to LVVTA for a Category Extension if they believe they have the knowledge and experience",
     ["Certify it anyway if it looks well made", "Ignore that modification and certify the rest", "Ask the owner to remove the modification first"],
     "ORS Ch.8, 1.2(1) Note 1: the certifier must either refer the owner to an appropriately categorised certifier or apply to LVVTA for a Category Extension."),
    ("Why must the fundamental checks at the start of an inspection (is it an LVV, which classification, modification dates, identifier, and so on) be made early?",
     "So effort is not wasted applying the process to a vehicle that is not an LVV, or applying the wrong process",
     ["Because they are the only checks that count towards the file review", "Because the owner must sign them before work starts", "Because they replace the photographic record"],
     "ORS Ch.8, 1.3 Note 1: the fundamental checks come early so time isn't wasted on a vehicle that isn't a low volume vehicle or by applying the incorrect process."),
    ("A certifier copies a vehicle's chassis number from the registration papers instead of looking at the vehicle. Is that acceptable?",
     "No — the certifier must sight the correctly affixed identifier on the vehicle", ["Yes, if the papers are original", "Yes, if the owner confirms it", "Yes, if a photo of the papers is taken"],
     "ORS Ch.8, 1.6 Note 1: recording the identifier or VIN from any other document or source is not acceptable as an alternative to sighting it on the vehicle."),
    ("A certifier finds evidence that a vehicle's identifier or VIN has been tampered with. What must happen?",
     "The vehicle must be referred to an NZTA-authorised Entry Certifier for validation of the identifier",
     ["The certifier re-stamps the correct number themselves", "The certification continues with a note on the file", "The owner signs a declaration and certification proceeds"],
     "ORS Ch.8, 1.6 Note 4: if tampering is established, the vehicle must be referred to an NZTA-authorised Entry Certifier for validation (using the LVV F005 form)."),
    ("The modifications on a vehicle are safe and compliant, but the workmanship is rough and crude in appearance. What do the inspection requirements expect?",
     "That the work is also carried out in a thorough, tidy and tradesman-like manner following sound automotive engineering principles",
     ["Nothing — appearance is not a certification matter", "That the owner repaints the affected area", "That LVVTA is notified of the builder's name"],
     "ORS Ch.8, 1.4(1)(b) and Note 2: crude work, even if compliant and safe, can bring the LVV certification system into disrepute."),
    ("Who must take the photographs in the required photographic record, and when?",
     "The LVV Certifier personally, at the time of the inspection", ["The vehicle owner, any time before submission", "The modifier, after finishing the work", "LVVTA staff, during the File Review"],
     "ORS Ch.8, 4.2(2): the photographs must be taken by the certifier personally and at the time of the inspection (except permitted post-rectification photographs)."),
    ("Does submitting a comprehensive photographic record shift responsibility for the vehicle's safety from the certifier to LVVTA?",
     "No — the certifier remains responsible for the correct assessment", ["Yes, once LVVTA accepts the file", "Yes, for modifications shown in the photographs", "Only for scratch-built vehicles"],
     "ORS Ch.8, 4.2 Note 1: submitting the documentation in no way reduces the certifier's responsibility or shifts responsibility for safety or compliance to LVVTA."),
    ("When may a certifier accept rectification photographs taken by the owner?",
     "After the primary inspection, when the rectification is minor, the photos clearly show it was fixed, and they are recorded as not taken by the certifier",
     ["Whenever the owner prefers it, for any rectification", "Only if the owner is a licensed motor trade business", "Never — the certifier must re-inspect every time"],
     "ORS Ch.8, 4.4(1): primary inspection complete, minor rectification, clear photographic evidence, and photos not taken by the certifier clearly recorded as such."),
    ("A vehicle has modified suspension. Can the certifier use a simple normal-function road test (a WoF-type test reaching about 50 kph)?",
     "No — a normal-function test cannot be used where steering, suspension, braking or drive-train were modified, so the full road test applies",
     ["Yes, because it is a quick check", "Yes, if the vehicle is lowered by under 40 mm", "Yes, if the owner accompanies the test"],
     "ORS Ch.8, 5.3 Notes 2 and 3: the normal function road test cannot be applied to a vehicle with any modification that could affect steering, suspension, braking or drive-train."),
    ("A certifier road-tests an unregistered vehicle. How must it be operated legally?",
     "With the use of a trade plate", ["With the owner's registration label", "With a printed copy of the LVV forms", "It cannot be road-tested at all"],
     "ORS Ch.8, 5.5(2)(d): in the case of an unregistered vehicle, operate it legally with the use of a trade plate."),
    ("A certifier is about to carry out cyclic brake performance testing. Where should it be done?",
     "On a quiet road with minimal traffic, with the road ahead and behind in both lanes free of traffic and pedestrians",
     ["On any main road at off-peak times", "In the workshop car park only", "On a busy road so the brakes are tested realistically"],
     "ORS Ch.8, 5.5(3): carry out the testing on a quiet road with minimal traffic and ensure the road ahead and behind, in both lanes, is free of traffic and pedestrians."),
    ("A commercial modifier is doing a series of identical modifications. What must the certifier do before starting any inspections?",
     "Check the relevant LVV Information Sheet and, if it applies, seek LVVTA approval first", ["Inspect the first vehicle and apply the result to the rest", "Start the inspections and notify LVVTA afterwards", "Do nothing — series work is exempt from the ORS"],
     "ORS Ch.8, 1.8(1): identify series-production modifications, check Information Sheet 01-2014, and seek LVVTA approval to apply the pre-approval process before commencing inspections."),
    ("What must a certifier do on finishing the final inspection of a vehicle?",
     "Fit the LVV Electronic Data Plate, affix any required labels, and submit the certification documentation to LVVTA", ["Hand the forms to the owner to lodge", "Wait for LVVTA to issue the plate", "Photograph the vehicle again and close the file"],
     "ORS Ch.8, 1.5(1): fit the LVV EDP, affix any LVVTA labels, and prepare and submit all required documentation to LVVTA."),
]


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
