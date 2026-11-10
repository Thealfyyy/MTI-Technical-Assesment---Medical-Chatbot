"""Tests for the Egyptian Franco-Arabic (Arabizi) normalizer.

Arabizi has no standard spelling, so the module supports an explicit list of
observed variants per Arabic word and never guesses: unrecognised tokens must
come back unchanged rather than half-converted.
"""

import pytest

from app.retrieval.franco_normalizer import (
    FRANCO_KEY_CONFLICTS,
    FRANCO_VOCAB_MAP,
    is_likely_franco,
    normalize_franco_to_arabic,
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Question words and the same sentence written three ways.
        ("eh el mada el fa3ala fel controloc", "إيه المادة الفعالة في controloc"),
        ("eih el madda el fa3la fe el controloc", "إيه المادة الفعالة في controloc"),
        ("2eh el mada el fa3ala f controloc", "إيه المادة الفعالة في controloc"),
        # Symptoms, including digit and letter spellings of the same word.
        ("3andy 7omoda", "عندي حموضة"),
        ("andi homouda", "عندي حموضة"),
        ("7omooda w sodaa3", "حموضة w صداع"),
        ("maghes w eshal", "مغص w إسهال"),
        # Pharmacy vocabulary.
        ("el gor3a kam", "الجرعة كام"),
        ("a3raad ganbeya", "أعراض جانبية"),
        ("mawane3 el est3mal", "موانع الاستعمال"),
        ("badayel el dawa", "بدائل الدواء"),
        # Franco brand spelling resolves to the Arabic form, which the alias
        # table then bridges to the corpus spelling.
        ("eh el badayel le brofen", "إيه البدائل ليه بروفين"),
    ],
)
def test_observed_spellings_normalize_to_arabic(query, expected):
    assert normalize_franco_to_arabic(query) == expected


def test_letter_elongation_and_hyphens_are_folded():
    assert normalize_franco_to_arabic("7omooooooda") == "حموضة"
    assert normalize_franco_to_arabic("fel-2olon") == "في القولون"


def test_unknown_tokens_are_kept_verbatim_not_half_transliterated():
    # The old implementation produced \"حabibi\": digits converted, Latin left in
    # place. Such a token matches neither the Arabic corpus nor a Latin name.
    assert normalize_franco_to_arabic("7abibi") == "7abibi"
    assert normalize_franco_to_arabic("3andy 7abibi") == "عندي 7abibi"


def test_doses_and_product_codes_are_not_transliterated():
    assert not is_likely_franco("Give 500 mg twice daily")
    assert not is_likely_franco("Is D3 a vitamin?")
    assert normalize_franco_to_arabic("500 mg w D3") == "500 mg w D3"


def test_english_questions_are_left_alone():
    query = "What are the common side effects of salbutamol?"
    assert not is_likely_franco(query)
    assert normalize_franco_to_arabic(query) == query


def test_a_single_franco_word_with_a_digit_is_detected():
    assert is_likely_franco("so5ona")
    assert normalize_franco_to_arabic("so5ona") == "سخونة"


def test_lookup_keys_do_not_collide_across_meanings():
    # Two spellings of different words may never share a normalized key: the
    # lookup would silently answer about the wrong body part or medicine.
    assert FRANCO_KEY_CONFLICTS == ()


def test_vocabulary_has_no_duplicate_spellings_for_different_words():
    seen: dict[str, str] = {}
    for spelling, arabic in FRANCO_VOCAB_MAP.items():
        assert spelling == spelling.casefold()
        assert seen.setdefault(spelling, arabic) == arabic
