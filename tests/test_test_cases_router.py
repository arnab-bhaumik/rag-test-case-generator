from api.routers.test_cases import validate_id_change


def test_validate_id_change_allows_unchanged_id():
    assert validate_id_change("TC_LOGIN_001", "TC_LOGIN_001", other_ids_in_run=["TC_LOGIN_002"], library_hit=None) is None


def test_validate_id_change_rejects_blank_id():
    error = validate_id_change("   ", "TC_LOGIN_001", other_ids_in_run=[], library_hit=None)
    assert error == "Test Case ID cannot be empty"


def test_validate_id_change_rejects_collision_with_another_case_in_run():
    error = validate_id_change("TC_LOGIN_002", "TC_LOGIN_001", other_ids_in_run=["TC_LOGIN_002"], library_hit=None)
    assert error is not None
    assert "already used by another test case in this run" in error


def test_validate_id_change_rejects_collision_with_a_different_library_case():
    error = validate_id_change(
        "TC_LOGIN_002", "TC_LOGIN_001", other_ids_in_run=[], library_hit={"id": "TC_LOGIN_002"}
    )
    assert error is not None
    assert "already used by a different test case in the library" in error


def test_validate_id_change_allows_when_library_hit_is_the_same_case():
    # Re-approving the same case after an id edit naturally finds itself in
    # the library — that's not a collision.
    error = validate_id_change("TC_LOGIN_005", "TC_LOGIN_001", other_ids_in_run=[], library_hit={"id": "TC_LOGIN_001"})
    assert error is None


def test_validate_id_change_allows_new_unique_id():
    error = validate_id_change("TC_LOGIN_099", "TC_LOGIN_001", other_ids_in_run=["TC_LOGIN_002"], library_hit=None)
    assert error is None


def test_validate_id_change_strips_whitespace_before_comparing():
    error = validate_id_change("  TC_LOGIN_001  ", "TC_LOGIN_001", other_ids_in_run=[], library_hit=None)
    assert error is None
