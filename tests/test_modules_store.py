import pytest

from src import modules_store


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Every test gets its own throwaway modules.json so tests can't see
    each other's state or touch the real project data."""
    monkeypatch.setattr(modules_store, "_STORE_PATH", tmp_path / "modules.json")


def test_list_manual_empty_when_no_file_exists():
    assert modules_store.list_manual() == []


def test_add_persists_module():
    modules_store.add("Checkout")
    assert modules_store.list_manual() == ["Checkout"]


def test_add_is_idempotent():
    modules_store.add("Checkout")
    modules_store.add("Checkout")
    assert modules_store.list_manual() == ["Checkout"]


def test_add_rejects_empty_name():
    with pytest.raises(ValueError):
        modules_store.add("   ")


def test_add_strips_whitespace():
    modules_store.add("  Checkout  ")
    assert modules_store.list_manual() == ["Checkout"]


def test_remove_deletes_module():
    modules_store.add("Checkout")
    modules_store.add("Auth")
    modules_store.remove("Checkout")
    assert modules_store.list_manual() == ["Auth"]


def test_remove_nonexistent_module_is_a_no_op():
    modules_store.add("Auth")
    modules_store.remove("DoesNotExist")
    assert modules_store.list_manual() == ["Auth"]


def test_rename_updates_manual_list():
    modules_store.add("Athu")
    modules_store.rename("Athu", "Auth")
    assert modules_store.list_manual() == ["Auth"]


def test_rename_adds_new_name_even_if_old_was_not_manually_tracked():
    # e.g. renaming a purely-derived module (never explicitly added)
    modules_store.rename("Payments", "Billing")
    assert modules_store.list_manual() == ["Billing"]


def test_rename_rejects_empty_new_name():
    modules_store.add("Auth")
    with pytest.raises(ValueError):
        modules_store.rename("Auth", "   ")


def test_rename_does_not_duplicate_when_new_name_already_manual():
    modules_store.add("Auth")
    modules_store.add("Authentication")
    modules_store.rename("Auth", "Authentication")
    assert modules_store.list_manual() == ["Authentication"]
