from pathlib import Path
from typing import Any

import orjson
from loguru import logger


def dump_json(obj: dict[str, Any], path: Path) -> None:
    if not path.parent.exists():
        path.mkdir(parents=True)

    with path.open("wb") as file:
        file.write(orjson.dumps(obj))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError
    try:
        with path.open("rb") as file:
            return orjson.loads(file.read())
    except orjson.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from {path}: {e}")
        return {}
