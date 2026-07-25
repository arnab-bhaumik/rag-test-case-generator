from openpyxl import Workbook

from src.ingestion.csv_test_case_loader import _resolve_column_map, _split_steps, load_csv, load_xlsx


def test_resolve_column_map_matches_exact_default_headers():
    headers = ["Test Case ID", "Title", "Preconditions", "Steps", "Expected Result", "Module", "Priority"]
    resolved = _resolve_column_map(headers)
    assert resolved == {
        "id": "Test Case ID",
        "title": "Title",
        "preconditions": "Preconditions",
        "steps": "Steps",
        "expected_result": "Expected Result",
        "module": "Module",
        "priority": "Priority",
    }


def test_resolve_column_map_matches_real_world_variant_headers():
    # Regression: a real uploaded file used "Test Scenario"/"Test Case Description"/
    # "Pre-conditions"/"Test Steps"/"Expected Result" — the old exact-match loader
    # silently dropped every one of these into blank fields.
    headers = [
        "Test Case ID",
        "Module",
        "Test Scenario",
        "Test Case Description",
        "Pre-conditions",
        "Test Steps",
        "Test Data",
        "Expected Result",
        "Priority",
        "Status",
    ]
    resolved = _resolve_column_map(headers)
    assert resolved["title"] == "Test Scenario"
    assert resolved["description"] == "Test Case Description"
    assert resolved["preconditions"] == "Pre-conditions"
    assert resolved["steps"] == "Test Steps"
    assert resolved["expected_result"] == "Expected Result"
    # Unmapped columns (Test Data, Status) are simply absent, not errors.
    assert "Test Data" not in resolved.values()


def test_resolve_column_map_is_case_and_hyphen_insensitive():
    headers = ["test case id", "PRE CONDITIONS", "expected results"]
    resolved = _resolve_column_map(headers)
    assert resolved["id"] == "test case id"
    assert resolved["preconditions"] == "PRE CONDITIONS"
    assert resolved["expected_result"] == "expected results"


def test_resolve_column_map_no_match_leaves_field_absent():
    resolved = _resolve_column_map(["Some Unrelated Column"])
    assert resolved == {}


def test_split_steps_strips_manual_numbering_and_bullets():
    raw = "1. Navigate to login page\n2. Enter credentials\n3. Click Login"
    assert _split_steps(raw) == ["Navigate to login page", "Enter credentials", "Click Login"]


def test_split_steps_strips_bullet_dashes():
    raw = "- Open the app\n- Tap login"
    assert _split_steps(raw) == ["Open the app", "Tap login"]


def test_split_steps_plain_lines_unaffected():
    raw = "Navigate to login page\nEnter valid username and password\nClick Login"
    assert _split_steps(raw) == ["Navigate to login page", "Enter valid username and password", "Click Login"]


def test_load_csv_with_real_world_headers_populates_every_field(tmp_path):
    content = (
        "Test Case ID,Module,Test Scenario,Test Case Description,Pre-conditions,Test Steps,Expected Result,Priority\n"
        'TC_LOGIN_001,Login,Successful login,Verify login works,"User is registered","1. Go to login\n'
        '2. Enter credentials",User is logged in,High\n'
    )
    path = tmp_path / "cases.csv"
    path.write_text(content, encoding="utf-8")

    cases = load_csv(path)

    assert len(cases) == 1
    tc = cases[0]
    assert tc.id == "TC_LOGIN_001"
    assert tc.title == "Successful login"
    assert tc.description == "Verify login works"
    assert tc.preconditions == "User is registered"
    assert tc.steps == ["Go to login", "Enter credentials"]
    assert tc.expected_result == "User is logged in"
    assert tc.module == "Login"
    assert tc.priority == "High"


def test_load_csv_skips_rows_missing_id(tmp_path):
    content = "Test Case ID,Title\n,Missing id row\nTC1,Has id\n"
    path = tmp_path / "cases.csv"
    path.write_text(content, encoding="utf-8")

    cases = load_csv(path)

    assert [c.id for c in cases] == ["TC1"]


def test_load_csv_no_id_column_returns_empty(tmp_path):
    path = tmp_path / "cases.csv"
    path.write_text("Foo,Bar\n1,2\n", encoding="utf-8")

    assert load_csv(path) == []


def test_load_xlsx_with_real_world_headers_populates_every_field(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Test Case ID", "Test Scenario", "Test Case Description", "Pre-conditions", "Test Steps", "Expected Result", "Priority"])
    ws.append(["TC1", "Scenario A", "Objective A", "Precond A", "1. Step one\n2. Step two", "Result A", "Medium"])
    path = tmp_path / "cases.xlsx"
    wb.save(path)

    cases = load_xlsx(path)

    assert len(cases) == 1
    tc = cases[0]
    assert tc.title == "Scenario A"
    assert tc.description == "Objective A"
    assert tc.preconditions == "Precond A"
    assert tc.steps == ["Step one", "Step two"]
    assert tc.expected_result == "Result A"
    assert tc.priority == "Medium"
