from src.ingestion.chunker import MAX_CHARS, _split_text, chunk_sections, chunk_text
from src.ingestion.doc_parser import DocSection


def test_chunk_text_short_text_produces_one_chunk():
    chunks = chunk_text("Users can reset their password.", source_type="jira", source_id="PROJ-1", module="Auth")

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == "Users can reset their password."
    assert chunk.source_type == "jira"
    assert chunk.source_id == "PROJ-1"
    assert chunk.module == "Auth"
    assert chunk.id == "PROJ-1::0"


def test_chunk_text_empty_text_produces_no_chunks():
    assert chunk_text("", source_type="jira", source_id="PROJ-1") == []
    assert chunk_text("   ", source_type="jira", source_id="PROJ-1") == []


def test_chunk_sections_preserves_heading_and_order():
    sections = [
        DocSection(heading="Overview", text="This feature lets users reset passwords.", order=0),
        DocSection(heading="Acceptance Criteria", text="A reset link expires after 30 minutes.", order=1),
    ]
    chunks = chunk_sections(sections, source_type="doc", source_id="design_doc")

    assert [c.section for c in chunks] == ["Overview", "Acceptance Criteria"]
    assert [c.order for c in chunks] == [0, 1]
    assert [c.id for c in chunks] == ["design_doc::0", "design_doc::1"]


def test_chunk_sections_skips_blank_sections():
    sections = [DocSection(heading="Empty", text="   ", order=0), DocSection(heading="Real", text="Has content.", order=1)]
    chunks = chunk_sections(sections, source_type="doc", source_id="d")

    assert len(chunks) == 1
    assert chunks[0].section == "Real"


def test_split_text_under_limit_returns_single_piece():
    assert _split_text("short text") == ["short text"]


def test_split_text_splits_long_text_on_paragraph_boundaries():
    paragraphs = [f"Paragraph {i} " + "x" * 100 for i in range(20)]
    text = "\n".join(paragraphs)

    pieces = _split_text(text, max_chars=300, overlap_chars=50)

    assert len(pieces) > 1
    assert all(len(p) <= 300 + 50 for p in pieces)  # allows for the carried-over overlap tail
    # nothing lost: every paragraph's distinguishing content appears somewhere
    for i in range(20):
        assert any(f"Paragraph {i} " in p for p in pieces)


def test_split_text_respects_overlap_between_consecutive_pieces():
    paragraphs = [f"P{i}-" + "x" * 200 for i in range(5)]
    text = "\n".join(paragraphs)

    pieces = _split_text(text, max_chars=250, overlap_chars=30)

    assert len(pieces) >= 2
    # the tail of each piece should reappear at the start of the next (the overlap)
    for prev, nxt in zip(pieces, pieces[1:]):
        tail = prev[-30:]
        assert nxt.startswith(tail)


def test_max_chars_default_is_reasonable_for_embeddings():
    # sanity guard: MAX_CHARS shouldn't silently regress to something absurd
    assert 200 <= MAX_CHARS <= 4000
