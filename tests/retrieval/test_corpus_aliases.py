"""Tests for the Arabic trade-name alias bridge used by retrieval."""

from app.retrieval.hybrid_search import CORPUS_NAME_ALIASES, expand_corpus_aliases


def test_arabic_brand_adds_the_corpus_spelling():
    expanded = expand_corpus_aliases("ايه بدائل بروفين؟")
    assert expanded.startswith("ايه بدائل بروفين؟")
    assert expanded.endswith("Brufen")


def test_definite_article_still_resolves():
    assert expand_corpus_aliases("جرعة الفولتارين") .endswith("Voltaren")


def test_multiple_brands_are_added_once_each():
    expanded = expand_corpus_aliases("الفرق بين بروفين و كاتافلام و بروفين")
    assert expanded.count("Brufen") == 1
    assert "Cataflam" in expanded


def test_query_without_a_brand_is_unchanged():
    query = "What are the common side effects of salbutamol?"
    assert expand_corpus_aliases(query) == query


def test_aliases_only_contain_latin_corpus_names():
    assert all(latin[:1].isupper() and latin.isascii() for latin in CORPUS_NAME_ALIASES.values())
