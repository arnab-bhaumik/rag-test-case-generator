from src.retrieval import retriever
from src.retrieval.retriever import _keyword_overlap, _rerank, retrieve_context


def test_keyword_overlap_no_shared_tokens_is_zero():
    assert _keyword_overlap("refund policy", "search filtering behavior") == 0.0


def test_keyword_overlap_full_match_is_one():
    assert _keyword_overlap("refund window", "the refund window is 30 days") == 1.0


def test_keyword_overlap_partial_match_is_fractional():
    # 1 of 2 query tokens ("refund") appears in the document
    assert _keyword_overlap("refund policy", "the refund window is 30 days") == 0.5


def test_keyword_overlap_empty_query_is_zero():
    assert _keyword_overlap("", "any document text") == 0.0


def test_keyword_overlap_is_case_insensitive():
    assert _keyword_overlap("REFUND", "a refund was issued") == 1.0


def test_rerank_prefers_lower_distance_when_overlap_equal():
    hits = [
        {"document": "unrelated text", "distance": 0.9},
        {"document": "unrelated text", "distance": 0.3},
    ]
    ranked = _rerank(hits, "some query")
    assert ranked[0]["distance"] == 0.3


def test_rerank_keyword_overlap_can_promote_a_farther_hit():
    # A hit with a slightly worse vector distance but a strong keyword match
    # should be able to outrank one with a marginally better distance but no
    # lexical overlap at all.
    hits = [
        {"document": "refund window is 30 days", "distance": 0.50},
        {"document": "totally unrelated content here", "distance": 0.45},
    ]
    ranked = _rerank(hits, "refund window")
    assert ranked[0]["document"] == "refund window is 30 days"


def test_retrieve_context_reranks_both_design_docs_and_examples(monkeypatch):
    design_hits = [
        {"document": "unrelated design doc content", "distance": 0.5, "metadata": {}},
        {"document": "refund window is 30 days", "distance": 0.6, "metadata": {}},
    ]
    example_hits = [
        {"document": "unrelated style example", "distance": 0.5, "metadata": {}, "id": "TC-1"},
        {"document": "refund window is 30 days", "distance": 0.6, "metadata": {}, "id": "TC-2"},
    ]

    monkeypatch.setattr(retriever, "query_design_docs", lambda *a, **k: design_hits)
    monkeypatch.setattr(retriever, "query_old_test_cases", lambda *a, **k: example_hits)

    ctx = retrieve_context("refund window", module="Payments")

    assert ctx.condition_text == "refund window"
    assert ctx.design_doc_hits[0]["document"] == "refund window is 30 days"
    assert ctx.example_test_case_hits[0]["document"] == "refund window is 30 days"


def test_retrieve_context_passes_module_through(monkeypatch):
    captured = {}

    def fake_query(text, n_results, module):
        captured["module"] = module
        return []

    monkeypatch.setattr(retriever, "query_design_docs", fake_query)
    monkeypatch.setattr(retriever, "query_old_test_cases", fake_query)

    retrieve_context("some condition", module="Auth")

    assert captured["module"] == "Auth"
