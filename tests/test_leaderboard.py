import json
import os
from datetime import date, datetime

from herdrill.leaderboard import (
    LEADERBOARD_PATH,
    Record,
    add_record,
    best_score,
    clean_name,
    load_records,
    make_record,
    save_records,
    top_records,
)


def test_canonical_leaderboard_path_uses_the_herdrill_name():
    assert LEADERBOARD_PATH == "~/.herdrill/leaderboard.json"


def test_records_are_ranked_and_include_name_score_and_date():
    records = [
        Record("Ada", 9, "2026-07-20"),
        Record("Mike", 14, "2026-07-21"),
    ]
    current = make_record(
        "  New   Player  ",
        11,
        recorded_on=datetime(2026, 7, 22, 14, 35, 9),
    )
    assert current == Record("New Player", 11, "2026-07-22", "14:35:09")
    assert current.timestamp == "2026-07-22 14:35:09"

    ranked = add_record(records, current)
    assert [record.score for record in ranked] == [14, 11, 9]
    assert best_score(ranked) == 14
    assert top_records(ranked) == ranked


def test_name_is_printable_compact_and_bounded():
    assert clean_name("  Mike\n  Yan  ") == "Mike Yan"
    assert clean_name("x" * 30) == "x" * 16
    assert clean_name("\x00\x01") == ""


def test_leaderboard_round_trips_atomically_and_ignores_bad_rows(tmp_path):
    path = tmp_path / "scores" / "best.json"
    records = [Record("Mike", 14, "2026-07-21", "14:35:09")]
    assert save_records(records, str(path))
    assert load_records(str(path)) == records
    assert not list(path.parent.glob("*.tmp"))

    payload = json.loads(path.read_text())
    assert payload["version"] == 2
    assert payload["records"][0]["time"] == "14:35:09"
    payload["records"].extend(
        [
            {"name": "", "score": 99, "date": "2026-07-21"},
            {"name": "Bad", "score": True, "date": "2026-07-21"},
            {"name": "Bad", "score": 20, "date": "yesterday"},
        ]
    )
    path.write_text(json.dumps(payload))
    assert load_records(str(path)) == records


def test_legacy_best_is_migrated_with_its_file_date(tmp_path):
    path = tmp_path / "best.json"
    path.write_text('{"best":27}\n')
    timestamp = datetime(2026, 7, 19, 12, 0).timestamp()
    os.utime(path, (timestamp, timestamp))

    assert load_records(str(path)) == [
        Record("Previous best", 27, "2026-07-19", "12:00:00")
    ]


def test_corrupt_leaderboard_is_empty_and_invalid_record_is_rejected(tmp_path):
    path = tmp_path / "best.json"
    path.write_text("not json")
    assert load_records(str(path)) == []
    assert make_record("", 3, recorded_on="2026-07-21") is None
    assert make_record("Mike", -1, recorded_on="2026-07-21") is None
    assert make_record("Mike", 3, recorded_on="not-a-date") is None
    assert make_record(
        "Mike",
        3,
        recorded_on=date(2026, 7, 21),
        recorded_time="25:00:00",
    ) is None
