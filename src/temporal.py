from datetime import date


def split_temporally(rows, train_end, validation_end):
    train_end, validation_end = date.fromisoformat(train_end), date.fromisoformat(validation_end)
    if train_end >= validation_end:
        raise ValueError("train_end must precede validation_end")
    dates = [row["match_date"] for row in rows]
    if any(current > following for current, following in zip(dates, dates[1:])):
        raise ValueError("rows must be sorted by match_date")
    if any(row.get("home_rank_date") and row["home_rank_date"] > row["match_date"] for row in rows):
        raise ValueError("home ranking timestamp exceeds match date")
    if any(row.get("away_rank_date") and row["away_rank_date"] > row["match_date"] for row in rows):
        raise ValueError("away ranking timestamp exceeds match date")
    train = [row for row in rows if row["match_date"] < train_end]
    validation = [row for row in rows if train_end <= row["match_date"] < validation_end]
    test = [row for row in rows if row["match_date"] >= validation_end]
    if train and validation and max(row["match_date"] for row in train) >= min(row["match_date"] for row in validation):
        raise ValueError("train/validation overlap")
    if validation and test and max(row["match_date"] for row in validation) >= min(row["match_date"] for row in test):
        raise ValueError("validation/test overlap")
    return train, validation, test
