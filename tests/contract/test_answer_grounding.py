from app.generation.grounding import check_answer_grounding


EVIDENCE = "Controloc – Pantoprazole. Proton Pump Inhibitors (PPIs) reduce gastric acid."


def test_arabic_paraphrase_with_source_drug_name_passes():
    result = check_answer_grounding(
        "المادة الفعالة في Controloc هي Pantoprazole، وهو من مجموعة PPIs.",
        EVIDENCE,
        "ايه المادة الفعالة في Controloc؟",
    )
    assert result.ok, result.unsupported


def test_arabic_answer_naming_an_absent_drug_fails():
    result = check_answer_grounding(
        "يمكن استخدام Controloc مع Aspirin.",
        EVIDENCE,
        "هل يمكن استخدام Controloc؟",
    )
    assert not result.ok
    assert "Aspirin" in result.unsupported


def test_answer_with_absent_number_fails():
    result = check_answer_grounding(
        "الجرعة هي 500 مجم يومياً.",
        "Diclofenac potassium 50 mg tablets",
        "كام جرعة الديكلوفيناك؟",
    )
    assert not result.ok
    assert "500" in result.unsupported


def test_answer_may_echo_a_number_from_the_question():
    result = check_answer_grounding(
        "For an adult of 70 kg the tablets in the passage are 50 mg.",
        "Diclofenac potassium 50 mg tablets",
        "Is 70 kg relevant?",
    )
    assert result.ok, result.unsupported


def test_english_answer_allows_sentence_initial_capital():
    result = check_answer_grounding(
        "Common side effects include tremors and palpitations.",
        "Tremors, palpitations and tachycardia are common.",
        "What are the side effects?",
    )
    assert result.ok, result.unsupported


def test_answer_written_in_cyrillic_look_alike_letters_fails():
    # Observed twice on the PC: the model transliterated a drug name into
    # Cyrillic ("الдиклофенак") inside an otherwise Arabic answer. No passage
    # contains those letters, so the answer is not supported by its sources.
    result = check_answer_grounding(
        "البدائل تشمل البروفين أو الдиклофенак.",
        "Trade Name: Brufen | Active Ingredient: Ibuprofen",
        "ايه بدائل Brufen؟",
    )
    assert not result.ok
    assert "диклофенак" in result.unsupported


def test_english_answer_with_absent_brand_name_fails():
    result = check_answer_grounding(
        "It is similar to Voltarol.",
        "Cataflam contains Diclofenac potassium.",
        "What is Cataflam?",
    )
    assert not result.ok
    assert "Voltarol" in result.unsupported
