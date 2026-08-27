import json
from pathlib import Path


def test_json_artifacts_are_nonempty_and_valid() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    packaged_resources = (
        repository_root / "src" / "dnd_engine" / "resources" / "rulesets"
    )
    artifacts = [
        path
        for directory in (packaged_resources, repository_root / "campaigns")
        for path in directory.rglob("*.json")
    ]

    for path in artifacts:
        assert path.stat().st_size > 0, f"JSON artifact is empty: {path.relative_to(repository_root)}"
        with path.open(encoding="utf-8") as artifact:
            json.load(artifact)
