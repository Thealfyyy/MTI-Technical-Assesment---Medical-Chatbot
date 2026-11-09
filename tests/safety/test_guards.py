from app.safety.guards import SafetyOutcome, classify_safety, detect_answer_language, response_language_for_query


def test_public_red_flag_cases_escalate():
    cases = [
        "How many mg of Voltaren can an adult take per day?",
        "عيان عنده ضيق نفس شديد وشفايفه زرقا، أديله Ventolin؟",
        "A patient accidentally swallowed a whole bottle of Panadol an hour ago but feels fine right now.",
        "طفل وزنه 12 كيلو وعنده سخونية، أديله كام سم Cetal شراب كل كام ساعة؟",
    ]
    assert all(classify_safety(case) == SafetyOutcome.ESCALATE for case in cases)


def test_non_red_flag_question_is_not_escalated():
    assert classify_safety("What is the active ingredient in Cataflam?") == SafetyOutcome.SAFE
    assert classify_safety("katably tab makin 100 mg 3ashan el-rebo, da sa7?") == SafetyOutcome.SAFE


def test_language_labels_follow_answer_script_and_franco_intent():
    assert detect_answer_language("باراسيتامول") == "ar"
    assert detect_answer_language("Use paracetamol") == "en"
    assert detect_answer_language("استخدم paracetamol") == "mixed"
    assert response_language_for_query("eh el mada el fa3ala?") == "ar"
