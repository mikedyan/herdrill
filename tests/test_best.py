import json

from herdrill_chatgpt.best import load_best, save_best


def test_missing_and_corrupt_best_are_zero(tmp_path):
    path = tmp_path / "best.json"
    assert load_best(str(path)) == 0
    path.write_text("not json")
    assert load_best(str(path)) == 0
    path.write_text('{"best": -1}')
    assert load_best(str(path)) == 0
    path.write_text('{"best": true}')
    assert load_best(str(path)) == 0


def test_best_round_trips_and_creates_parent(tmp_path):
    path = tmp_path / "new" / "best.json"
    assert save_best(17, str(path))
    assert load_best(str(path)) == 17
    assert json.loads(path.read_text()) == {"best": 17}
    assert not list(path.parent.glob("*.tmp"))


def test_invalid_score_is_not_written(tmp_path):
    path = tmp_path / "best.json"
    assert not save_best(-2, str(path))
    assert not path.exists()
