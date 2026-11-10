from app.safety.guards import (
    SafetyOutcome,
    classify_safety,
    detect_answer_language,
    response_language_for_query,
    static_reply_language,
)


def test_public_red_flag_cases_escalate():
    cases = [
        "How many mg of Voltaren can an adult take per day?",
        "عيان عنده ضيق نفس شديد وشفايفه زرقا، أديله Ventolin؟",
        "A patient accidentally swallowed a whole bottle of Panadol an hour ago but feels fine right now.",
        "طفل وزنه 12 كيلو وعنده سخونية، أديله كام سم Cetal شراب كل كام ساعة؟",
    ]
    assert all(classify_safety(case) == SafetyOutcome.ESCALATE for case in cases)


def test_franco_red_flags_escalate_through_normalization():
    # The same emergency written in three Arabizi spellings, plus a personal
    # dose question whose drug name sits between "dose" and "how much".
    cases = [
        "3ayan 3ando zay2 nafas shadeed w shafaifo zar2a, adilo ventolin?",
        "3andy zay2 nafas shadid",
        "shafayef zar2a w day2 nafas",
        "el gor3a bta3et controloc kam fel youm?",
        "الجرعة بتاعة كونترولوك كام في اليوم؟",
    ]
    assert all(classify_safety(case) == SafetyOutcome.ESCALATE for case in cases)


def test_non_red_flag_question_is_not_escalated():
    assert classify_safety("What is the active ingredient in Cataflam?") == SafetyOutcome.SAFE
    assert classify_safety("katably tab makin 100 mg 3ashan el-rebo, da sa7?") == SafetyOutcome.SAFE
    assert classify_safety("a3rad ganbeya le salbutamol") == SafetyOutcome.SAFE
    assert classify_safety("eh el badayel le brofen?") == SafetyOutcome.SAFE


def test_language_labels_follow_answer_script_and_franco_intent():
    assert detect_answer_language("باراسيتامول") == "ar"
    assert detect_answer_language("Use paracetamol") == "en"
    # Arabic prose that names a drug in Latin script is still an Arabic answer.
    assert detect_answer_language("استخدم paracetamol") == "ar"
    assert detect_answer_language("Use paracetamol first for mild pain and fever و بحذر") == "mixed"
    assert response_language_for_query("eh el mada el fa3ala?") == "ar"
    # The model still gets the 'mixed' hint so it keeps English drug names, but a
    # fixed reply to an Arabic-dominant question is labelled ar.
    assert response_language_for_query("عيان عنده ضيق نفس شديد وشفايفه زرقا، أديله Ventolin؟") == "mixed"
    assert static_reply_language("عيان عنده ضيق نفس شديد وشفايفه زرقا، أديله Ventolin؟") == "ar"
    assert static_reply_language("Use paracetamol first for mild pain and fever و بحذر") == "mixed"
