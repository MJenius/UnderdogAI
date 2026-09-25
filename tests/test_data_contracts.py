import csv
import io

import pytest

from src.data_contracts import DataContractError, validate_csv


MATCH_HEADER = "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"


def test_contract_accepts_valid_match_and_rejects_bad_values():
    valid = MATCH_HEADER + "2022-11-20,Qatar,Ecuador,0,2,FIFA World Cup,Doha,Qatar,TRUE\n"
    assert len(validate_csv("results.csv", valid)) == 1
    for bad in (
        valid.replace("home_score,away_score", "away_score,home_score"),
        valid.replace(",0,2,", ",-1,2,"),
        valid.replace("2022-11-20", "2099-11-20"),
        valid.replace(",TRUE", ",maybe"),
        valid.replace(",Qatar,Ecuador,", ",Qatar,Qatar,"),
    ):
        with pytest.raises(DataContractError):
            validate_csv("results.csv", bad)


def test_contract_rejects_schema_drift_and_nonfinite_rank_points():
    header = "rank,country_full,country_abrv,total_points,previous_points,rank_change,confederation,rank_date\n"
    good = header + "1,Argentina,ARG,1850,1840,0,CONMEBOL,2022-10-06\n"
    assert len(validate_csv("fifa_ranking-2026-01-19.csv", good)) == 1
    with pytest.raises(DataContractError):
        validate_csv("fifa_ranking-2026-01-19.csv", good.replace("1850", "NaN"))
    with pytest.raises(DataContractError):
        validate_csv("results.csv", MATCH_HEADER.replace("country", "nation") + "2022-11-20,Q,E,0,1,WC,Doha,Qatar,TRUE\n")
