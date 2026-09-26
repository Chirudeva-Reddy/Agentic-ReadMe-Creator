import pytest
from cli import split


def test_even_split():
    assert split(100, 4, tip_pct=0) == 25.0


def test_tip_included():
    assert split(100, 2, tip_pct=20) == 60.0


def test_rejects_zero_people():
    with pytest.raises(ValueError):
        split(10, 0)
