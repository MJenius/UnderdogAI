import csv
import hashlib
import io
import math
from datetime import date


class DataContractError(ValueError):
    pass


CONTRACTS = {
    "results.csv": {
        "required": ("date", "home_team", "away_team", "home_score", "away_score", "tournament", "city", "country", "neutral"),
        "optional": ("Unnamed: 0",),
        "nullable": ("home_score", "away_score"),
        "strings": ("home_team", "away_team", "tournament", "city", "country"),
        "integers": ("home_score", "away_score"),
        "date": "date",
        "ranges": {"home_score": (0, 100), "away_score": (0, 100)},
    },
    "shootouts.csv": {
        "required": ("date", "home_team", "away_team", "winner", "first_shooter"),
        "strings": ("home_team", "away_team", "winner"),
        "date": "date",
    },
    "fifa_ranking-2026-01-19.csv": {
        "required": ("rank", "country_full", "country_abrv", "total_points", "previous_points", "rank_change", "confederation", "rank_date"),
        "optional": ("id", "Unnamed: 0", ""),
        "nullable": ("rank", "total_points", "previous_points", "rank_change"),
        "strings": ("country_full", "country_abrv", "confederation"),
        "integers": ("rank", "rank_change"),
        "floats": ("total_points", "previous_points"),
        "date": "rank_date",
        "ranges": {"rank": (1, 300), "rank_change": (-300, 300), "total_points": (0, 10000), "previous_points": (0, 10000)},
    },
}


def validate_csv(filename, content):
    if filename not in CONTRACTS:
        raise DataContractError(f"unknown dataset schema: {filename}")
    contract = CONTRACTS[filename]
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise DataContractError(f"{filename}: missing header")
    expected = list(contract["required"])
    if filename == "fifa_ranking-2026-01-19.csv" and reader.fieldnames == ["", *expected]:
        expected = reader.fieldnames
    if filename == "results.csv" and reader.fieldnames == ["Unnamed: 0", *expected]:
        expected = reader.fieldnames
    if reader.fieldnames != expected:
        raise DataContractError(f"{filename}: schema/order mismatch expected={expected} actual={reader.fieldnames}")
    missing = set(contract["required"]) - set(reader.fieldnames)
    unexpected = set(reader.fieldnames) - set(contract["required"]) - set(contract.get("optional", ())) - {""}
    if missing or unexpected:
        raise DataContractError(f"{filename}: schema mismatch missing={sorted(missing)} unexpected={sorted(unexpected)}")
    rows = []
    for line, row in enumerate(reader, 2):
        if None in row:
            raise DataContractError(f"{filename}:{line}: extra columns")
        try:
            for field in contract["required"]:
                if not row[field] or not row[field].strip():
                    if field in contract.get("nullable", ()):
                        continue
                    if filename == "shootouts.csv" and field == "first_shooter":
                        continue
                    if filename == "fifa_ranking-2026-01-19.csv" and field in {"total_points", "previous_points", "rank_change"}:
                        continue
                    raise ValueError(f"{field} required")
            for field in contract["strings"]:
                if not row[field] or not row[field].strip():
                    raise ValueError(f"{field} required")
            if "first_shooter" in row and row["first_shooter"] and row["first_shooter"] not in (row["home_team"], row["away_team"]):
                raise ValueError("first_shooter must be a match team")
            for field in contract.get("integers", ()):
                if row[field].strip().upper() in {"NA", "NULL"} and field in contract.get("nullable", ()):
                    continue
                if field in contract.get("nullable", ()) and not row[field]:
                    continue
                value = int(float(row[field]))
                low, high = contract["ranges"][field]
                if not low <= value <= high:
                    raise ValueError(f"{field} outside [{low}, {high}]")
            for field in contract.get("floats", ()):
                if row[field].strip().upper() in {"NA", "NULL"} and field in contract.get("nullable", ()):
                    continue
                if row[field]:
                    value = float(row[field])
                    if not math.isfinite(value):
                        raise ValueError(f"{field} must be finite")
                    low, high = contract["ranges"][field]
                    if not low <= value <= high:
                        raise ValueError(f"{field} outside [{low}, {high}]")
            if "neutral" in row and row["neutral"].upper() not in {"TRUE", "FALSE"}:
                raise ValueError("neutral must be TRUE or FALSE")
            stamp = date.fromisoformat(row[contract["date"]])
            if stamp > date.today():
                raise ValueError(f"{contract['date']} is in the future")
            if "home_team" in row and row["home_team"].strip() == row["away_team"].strip():
                raise ValueError("teams must differ")
            if filename == "shootouts.csv" and row["winner"] not in (row["home_team"], row["away_team"]):
                raise ValueError("winner must be a match team")
        except (TypeError, ValueError) as exc:
            raise DataContractError(f"{filename}:{line}: {exc}") from exc
        rows.append(row)
    if not rows:
        raise DataContractError(f"{filename}: empty dataset")
    return rows


def schema_fingerprint(filename):
    return hashlib.sha256(",".join(CONTRACTS[filename]["required"]).encode()).hexdigest()
