"""
Contains the base class for project structures.

To run integration tests with 'doctests':
python -m dbt_pipeline_utils.p_utils.general
"""

import yaml
import re
import pandas as pd
from pathlib import Path
import hashlib
from typing import Iterable
from dbt_pipeline_utils.p_utils.common import MAX_IDENTIFIER_LEN, SAFE_CHARS

from dbt_pipeline_utils import logger


def read_file(filepath):
    path = Path(filepath).resolve()

    if not path.exists():
        logger.warning(f"File does not exist: {path}")
        raise FileNotFoundError(f"File does not exist: {path}")

    file_handlers = {
        ".yaml": lambda: yaml.safe_load(path.read_text(encoding="utf-8")),
        ".yml":  lambda: yaml.safe_load(path.read_text(encoding="utf-8")),
        ".csv":  lambda: pd.read_csv(path, header=0, dtype="string"),
        ".xlsx": lambda: pd.read_excel(path, header=0),
        ".sql":  lambda: path.read_text(encoding="utf-8"),
        ".md":   lambda: path.read_text(encoding="utf-8"),
    }

    file_ext = path.suffix.lower()

    if file_ext not in file_handlers:
        raise ValueError(f"Unsupported file type: {file_ext}")

    logger.debug(f"Reading {file_ext} from file: {path}")

    data = file_handlers[file_ext]()

    logger.debug(f"Read {path} successful")
    return data


def write_file(
    filepath: Path,
    data,
    *,
    mode: str = "overwrite",
) -> None:
    filepath = Path(filepath).resolve()

    logger.debug(f"write_file '{mode}' mode. file: '{tail_path(filepath,depth=3)}'")

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)

        suffix = filepath.suffix.lower()

        if mode not in {"create", "overwrite", "merge"}:
            raise ValueError(f"Invalid mode: {mode}")

        # CREATE
        if mode == "create" and filepath.exists():
            logger.debug(f"File exists, skipping create: {filepath}")
            return

        # YAML FILES
        if suffix in {".yml", ".yaml"}:
            if mode == "merge" and filepath.exists():
                with filepath.open("r", encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}

                if not isinstance(existing, dict):
                    raise ValueError(f"Cannot merge into non-dict YAML: {filepath}")

                data = deep_merge(existing, data)

            with filepath.open("w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    sort_keys=False,
                    default_flow_style=False,
                    indent=2,
                )
            return

        # TEXT FILES
        if suffix in {".md", ".sh", ".py"}:
            file_mode = "a" if mode == "merge" else "w"
            with filepath.open(file_mode, encoding="utf-8") as f:
                f.write(data)
            return

        # SQL FILES - Don't overwrite.
        if suffix in {".sql"} and filepath.exists():
            return
        elif suffix in {".sql"} and not filepath.exists():
            file_mode = "w"
            with filepath.open(file_mode, encoding="utf-8") as f:
                f.write(data)
            return

        # CSV
        if suffix == ".csv":
            data.to_csv(filepath, index=False)
            return

        raise ValueError(f"Unsupported file type: {suffix}")

    except Exception as e:
        logger.exception(
            "Unexpected error in write_file 'path': {filepath}, 'mode': {mode}"
        )
        raise

def deep_merge(existing: dict, incoming: dict) -> dict:
    for key, value in incoming.items():
        if (
            key in existing
            and isinstance(existing[key], dict)
            and isinstance(value, dict)
        ):
            deep_merge(existing[key], value)
        else:
            existing[key] = value
    return existing


def tail_path(path: Path, depth: int = 2) -> str:
    parts = path.parts
    return Path(*parts[-(depth + 1) :]).as_posix()


def clean_string(input: str) -> str:

    cleaned = SAFE_CHARS.sub("_", input).lower()
    return re.sub(r"_+", "_", cleaned).strip("_")


def shorten_identifier(input: str, max_len: int = MAX_IDENTIFIER_LEN) -> str:
    """
    Truncate a string to `max_len` characters while preserving uniqueness by
    appending an 8-character hash suffix.

    Behavior:
    - If input length <= max_len → returned unchanged
    - If input length > max_len → prefix + '_' + 8-char hash

    Doctest
    -------
    >>> shorten_identifier("a" * 10, max_len=10)
    'aaaaaaaaaa'

    >>> out = shorten_identifier("x" * 80, max_len=20)
    >>> len(out) <= 20
    True

    """
    if len(input) <= max_len:
        return input

    # Stable hash from full input
    s_hash = hashlib.md5(input.encode("utf-8")).hexdigest()[:8]

    # Truncate original input
    keep = max_len - len(s_hash) - 1
    shortened = f"{input[:keep]}_{s_hash}"

    logger.debug(
        "Identifier length exceeded %s chars; shortened '%s' -> '%s'",
        max_len,
        input,
        shortened,
    )

    return shortened


def normalize_string(input: str | Path, *, extension: str = "drop") -> str:
    """
    Use case: When table names match the associated dd name. This SHOULD be the
    case for intermediate and export models. Not applicable for
    raw/src datafiles and dds.

    Lowers
    Ensures names contain only letters, numbers and underscores.

    extension : {'drop', 'keep'}
    - 'drop' : normalize only the stem
    - 'keep' : normalize the stem and reattach the (lowercased) extension

    Doctest
    -------
    >>> normalize_string('AccessPolicy_external_id-dd.csv', extension='keep')
    'accesspolicy_external_id_dd.csv'

    >>> normalize_string('SomeDatafileIdentifier24601).csv')
    'somedatafileidentifier24601'

    """
    s_input = str(input)
    p_input = Path(s_input)

    has_ext = bool(p_input.suffix)
    stem = p_input.stem if has_ext else s_input
    ext = p_input.suffix.lower() if has_ext else ""

    normalized = clean_string(stem)

    if extension == "keep" and has_ext:
        return f"{normalized}{ext}"

    return normalized


def normalize_name(
    input: str | Path | Iterable[str | None],
    *,
    trailing: bool = False,
    extension: str = "drop",
) -> str:
    """
    Join a list of parts with underscores and normalize the result.

    - Ignores None/empty values
    - Uses underscores as the delimiter
    - Optionally appends a trailing underscore
    - Normalizes via normalize_name()

    Parameters
    ----------
    trailing : bool
        If True, append a trailing underscore.

    Doctest
    -------
    >>> normalize_name(['synthetic', 'int'], trailing=True)
    'synthetic_int_'

    >>> normalize_name(['AccessPolicy', 'stg.csv'], trailing=True)
    'accesspolicy_stg_'

    >>> normalize_name(['project', None, 'table!24601', 'exp.csv'], extension='keep')
    'project_table_24601_exp.csv'

    """

    if isinstance(input, Path):
        input = str(input)
    elif isinstance(input, str):
        pass
    else:
        input = "_".join(str(i) for i in input if i)

    result = normalize_string(input, extension=extension)

    if trailing and not result.endswith("_"):
        result += "_"

    return result
