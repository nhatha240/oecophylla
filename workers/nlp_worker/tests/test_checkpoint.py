from pathlib import Path

from app.rebuild import JsonCheckpoint


def test_json_checkpoint_roundtrip_is_private_and_atomic(tmp_path: Path) -> None:
    path = tmp_path / "state" / "checkpoint.json"
    checkpoint = JsonCheckpoint(path)

    assert checkpoint.load() is None
    checkpoint.save("opaque-cursor")

    assert checkpoint.load() == "opaque-cursor"
    assert path.stat().st_mode & 0o777 == 0o600
    assert not path.with_suffix(".tmp").exists()
