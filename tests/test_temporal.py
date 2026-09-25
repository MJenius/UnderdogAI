from datetime import date

import pytest

from src.temporal import split_temporally


def row(day, home_rank_day=None, away_rank_day=None):
    return {"match_date": date.fromisoformat(day), "home_rank_date": date.fromisoformat(home_rank_day) if home_rank_day else None,
            "away_rank_date": date.fromisoformat(away_rank_day) if away_rank_day else None}


def test_temporal_split_is_disjoint_and_ordered():
    train, validation, test = split_temporally(
        [row("2020-01-01"), row("2021-12-31"), row("2022-01-01"), row("2023-01-01")], "2022-01-01", "2023-01-01"
    )
    assert (len(train), len(validation), len(test)) == (2, 1, 1)


@pytest.mark.parametrize("rows", [
    [row("2022-01-01", "2022-02-01")],
    [row("2021-01-01"), row("2020-01-01")],
])
def test_temporal_split_fails_closed(rows):
    with pytest.raises(ValueError):
        split_temporally(rows, "2022-01-01", "2023-01-01")
