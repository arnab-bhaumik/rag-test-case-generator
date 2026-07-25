from src.models.schemas import TestCase
from src.vectorstore import test_cases_store
from src.vectorstore.test_cases_store import (
    UNSORTED_SESSION_ID,
    _document,
    _parse_document,
    _where,
    build_id_prefix,
    list_sessions,
    next_sequence_ids,
    normalize_module_for_id,
)


def _tc(**kwargs) -> TestCase:
    defaults = dict(id="TC-1", title="Login works", preconditions="User exists", steps=["Open app", "Log in"], expected_result="Dashboard shown")
    defaults.update(kwargs)
    return TestCase(**defaults)


def test_document_and_parse_document_round_trip():
    tc = _tc(description="Verifies login succeeds with valid credentials")
    parsed = _parse_document(_document(tc))
    assert parsed["description"] == tc.description
    assert parsed["preconditions"] == tc.preconditions
    assert parsed["steps"] == tc.steps
    assert parsed["expected_result"] == tc.expected_result


def test_parse_document_without_description_line_defaults_to_blank():
    # Regression: entries written before `description` existed have no
    # "Description:" line at all — parsing must not choke on that.
    legacy_document = "Title: Login works\nPreconditions: User exists\nSteps:\n1. Open app\nExpected Result: Dashboard shown"
    parsed = _parse_document(legacy_document)
    assert parsed["description"] == ""
    assert parsed["preconditions"] == "User exists"
    assert parsed["steps"] == ["Open app"]
    assert parsed["expected_result"] == "Dashboard shown"


def test_parse_document_handles_multiple_steps_and_multiline_expected_result():
    tc = _tc(steps=["Step one", "Step two", "Step three"], expected_result="Line one\nLine two")
    parsed = _parse_document(_document(tc))
    assert parsed["steps"] == ["Step one", "Step two", "Step three"]
    assert parsed["expected_result"] == "Line one\nLine two"


def test_parse_document_empty_steps_gives_empty_list():
    tc = _tc(steps=[])
    parsed = _parse_document(_document(tc))
    assert parsed["steps"] == []


def test_parse_document_on_malformed_text_returns_blanks_not_a_crash():
    parsed = _parse_document("not in the expected format at all")
    assert parsed == {"description": "", "preconditions": "", "steps": [], "expected_result": ""}


def test_where_no_filters_is_none():
    assert _where(None, None) is None


def test_where_module_only():
    assert _where("Auth", None) == {"module": "Auth"}


def test_where_session_id_only():
    assert _where(None, "run-123") == {"session_id": "run-123"}


def test_where_module_and_session_id_combine_with_and():
    assert _where("Auth", "run-123") == {"$and": [{"module": "Auth"}, {"session_id": "run-123"}]}


def test_where_unsorted_pseudo_session_id_splits_into_session_and_source():
    result = _where(None, f"{UNSORTED_SESSION_ID}:library")
    assert result == {"$and": [{"session_id": ""}, {"source": "library"}]}


class _FakeCollection:
    def __init__(self, ids, metadatas):
        self._ids = ids
        self._metadatas = metadatas
        self.updated_ids: list[str] = []
        self.updated_metadatas: list[dict] = []

    def get(self, limit=None, where=None):
        return {"ids": self._ids, "metadatas": self._metadatas}

    def update(self, ids, metadatas):
        self.updated_ids = ids
        self.updated_metadatas = metadatas


def test_list_sessions_groups_by_session_id_and_counts(monkeypatch):
    fake = _FakeCollection(
        ids=["a", "b", "c"],
        metadatas=[
            {"session_id": "run-1", "session_label": "SCRUM-8", "session_created_at": "2026-01-01T00:00:00Z", "source": "generated"},
            {"session_id": "run-1", "session_label": "SCRUM-8", "session_created_at": "2026-01-01T00:00:00Z", "source": "generated"},
            {"session_id": "run-2", "session_label": "SCRUM-9", "session_created_at": "2026-01-02T00:00:00Z", "source": "generated"},
        ],
    )
    monkeypatch.setattr(test_cases_store, "_collection", lambda: fake)

    sessions = list_sessions()

    by_id = {s["session_id"]: s for s in sessions}
    assert by_id["run-1"]["count"] == 2
    assert by_id["run-2"]["count"] == 1
    # newest session_created_at first
    assert sessions[0]["session_id"] == "run-2"


def test_list_sessions_buckets_legacy_entries_by_source(monkeypatch):
    fake = _FakeCollection(
        ids=["a", "b"],
        metadatas=[
            {"session_id": "", "session_label": "", "session_created_at": "", "source": "library"},
            {"session_id": "", "session_label": "", "session_created_at": "", "source": "generated"},
        ],
    )
    monkeypatch.setattr(test_cases_store, "_collection", lambda: fake)

    sessions = list_sessions()

    session_ids = {s["session_id"] for s in sessions}
    assert f"{UNSORTED_SESSION_ID}:library" in session_ids
    assert f"{UNSORTED_SESSION_ID}:generated" in session_ids
    for s in sessions:
        assert s["session_label"] == "Unsorted (before session tracking)"


def test_list_sessions_backfills_metadata_missing_session_id_key(monkeypatch):
    # A doc written before session_id existed has no key at all — not an
    # empty one. list_sessions() must stamp the key in so _where()'s
    # equality filter can find it on a later query (Chroma only matches
    # documents where the key is present).
    fake = _FakeCollection(ids=["legacy-1"], metadatas=[{"source": "library"}])
    monkeypatch.setattr(test_cases_store, "_collection", lambda: fake)

    list_sessions()

    assert fake.updated_ids == ["legacy-1"]
    assert fake.updated_metadatas[0]["session_id"] == ""
    assert fake.updated_metadatas[0]["session_label"] == ""
    assert fake.updated_metadatas[0]["session_created_at"] == ""


def test_list_sessions_no_backfill_when_session_id_key_already_present(monkeypatch):
    fake = _FakeCollection(ids=["a"], metadatas=[{"session_id": "", "source": "library"}])
    monkeypatch.setattr(test_cases_store, "_collection", lambda: fake)

    list_sessions()

    assert fake.updated_ids == []


def test_normalize_module_for_id_uppercases_and_replaces_spaces():
    assert normalize_module_for_id("Payments") == "PAYMENTS"
    assert normalize_module_for_id("Payment Gateway") == "PAYMENT_GATEWAY"


def test_normalize_module_for_id_strips_punctuation():
    assert normalize_module_for_id("Auth & Login!") == "AUTH_LOGIN"


def test_normalize_module_for_id_blank_or_none_is_not_defined():
    assert normalize_module_for_id(None) == "NOT_DEFINED"
    assert normalize_module_for_id("   ") == "NOT_DEFINED"


def test_build_id_prefix():
    assert build_id_prefix("Payments") == "TC_PAYMENTS_"
    assert build_id_prefix(None) == "TC_NOT_DEFINED_"


def test_next_sequence_ids_starts_at_one_when_library_empty(monkeypatch):
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [])

    ids = next_sequence_ids("Auth", 3)

    assert ids == ["TC_AUTH_001", "TC_AUTH_002", "TC_AUTH_003"]


def test_next_sequence_ids_continues_from_highest_existing_number(monkeypatch):
    monkeypatch.setattr(
        test_cases_store,
        "list_all",
        lambda **kwargs: [{"id": "TC_LOGIN_001"}, {"id": "TC_LOGIN_002"}, {"id": "TC_PAYMENTS_005"}],
    )

    assert next_sequence_ids("Login", 2) == ["TC_LOGIN_003", "TC_LOGIN_004"]


def test_next_sequence_ids_ignores_ids_from_a_different_prefix(monkeypatch):
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [{"id": "TC_PAYMENTS_099"}])

    assert next_sequence_ids("Login", 1) == ["TC_LOGIN_001"]


def test_next_sequence_ids_accounts_for_extra_existing_ids_not_yet_in_library(monkeypatch):
    # Simulates not-yet-approved siblings minted earlier in the same run.
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [{"id": "TC_LOGIN_001"}])

    ids = next_sequence_ids("Login", 2, extra_existing_ids={"TC_LOGIN_002", "TC_LOGIN_003"})

    assert ids == ["TC_LOGIN_004", "TC_LOGIN_005"]


def test_next_sequence_ids_zero_count_returns_empty_list(monkeypatch):
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [])
    assert next_sequence_ids("Auth", 0) == []


def test_next_sequence_ids_custom_prefix_used_verbatim_ignoring_module(monkeypatch):
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [])

    ids = next_sequence_ids("Login", 2, custom_prefix="DEMND002_Reg_TC_")

    # No separator inserted, no module-derived prefix — exactly what was typed.
    assert ids == ["DEMND002_Reg_TC_001", "DEMND002_Reg_TC_002"]


def test_next_sequence_ids_custom_prefix_continues_from_existing_numbers(monkeypatch):
    monkeypatch.setattr(
        test_cases_store,
        "list_all",
        lambda **kwargs: [{"id": "DEMND002_Reg_TC_001"}, {"id": "DEMND002_Reg_TC_002"}, {"id": "TC_LOGIN_099"}],
    )

    ids = next_sequence_ids("Login", 1, custom_prefix="DEMND002_Reg_TC_")

    assert ids == ["DEMND002_Reg_TC_003"]


def test_next_sequence_ids_custom_prefix_also_checks_extra_existing_ids(monkeypatch):
    monkeypatch.setattr(test_cases_store, "list_all", lambda **kwargs: [{"id": "DEMND002_Reg_TC_001"}])

    ids = next_sequence_ids("Login", 1, extra_existing_ids={"DEMND002_Reg_TC_002"}, custom_prefix="DEMND002_Reg_TC_")

    assert ids == ["DEMND002_Reg_TC_003"]
