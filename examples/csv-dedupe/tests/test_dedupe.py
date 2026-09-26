from cli import dedupe

ROWS = [
    {"email": "ana@x.com", "name": "Ana"},
    {"email": "ana@x.com", "name": "Ana"},
    {"email": "ANA@x.com ", "name": "Ana M."},
    {"email": "bo@x.com", "name": "Bo"},
]


def test_exact_duplicates_removed():
    assert len(dedupe(ROWS)) == 3


def test_key_column_is_case_insensitive():
    assert [r["name"] for r in dedupe(ROWS, key="email")] == ["Ana", "Bo"]


def test_keeps_first_occurrence():
    assert dedupe(ROWS)[0] is ROWS[0]


def test_empty_input():
    assert dedupe([]) == []
