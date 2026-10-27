"""
Standalone data-dictionary -> dbt models.yml generation.

Every function here takes explicit file paths and plain values as arguments.
None of them depend on StudyConfig/PipelineObject/StructureBC or any other
pipeline stage - each does exactly one task. Compose them (e.g. loop over a
directory of data dictionaries) from a bash script or a small Python script
rather than a shared project config.
"""

import io
import re
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from dbt_pipeline_utils.p_utils.common import DD_FORMATS
from dbt_pipeline_utils.p_utils.dbt_testing import DbtTesting
from dbt_pipeline_utils.p_utils.dd_sources import (
    DDSource,
    InMemoryDataDictionary,
    dd_source_descriptor,
    log_dd_versions,
    pull_release_dd,
    resolve_dd_sources as _resolve_dd_filepaths,
)
from dbt_pipeline_utils.p_utils.files import (
    normalize_name,
    read_file,
    shorten_identifier,
    write_file,
)


def _as_str_or_none(value):
    return None if value is None or pd.isna(value) else str(value)


def _extract_columns(df: pd.DataFrame, dd_format: str) -> list[dict]:
    """Shared column-extraction logic for both file-based and in-memory data dictionaries."""
    if dd_format not in DD_FORMATS:
        raise ValueError(
            f"Unsupported dd_format '{dd_format}'. Options: {list(DD_FORMATS)}"
        )

    column_map = DD_FORMATS[dd_format]

    if df is None:
        raise ValueError("No data read from data dictionary")

    df = df.astype("string").where(pd.notna(df), None)

    columns = []
    for _, row in df.iterrows():
        variable_name = _as_str_or_none(row.get(column_map.get("variable_name")))
        if not variable_name:
            continue

        formatted_variable_name = normalize_name(variable_name, extension="drop")

        src_variable_name = _as_str_or_none(
            row.get(column_map.get("src_variable_name"), formatted_variable_name)
        ) or formatted_variable_name

        columns.append(
            {
                "variable_name": variable_name,
                "formatted_variable_name": formatted_variable_name,
                "description": _as_str_or_none(row.get(column_map.get("description"))),
                "data_type": _as_str_or_none(row.get(column_map.get("data_type"))),
                "enumerations": _as_str_or_none(row.get(column_map.get("enumerations"))),
                "comment": _as_str_or_none(row.get(column_map.get("comment"))),
                "src_variable_name": src_variable_name,
                "tests": _as_str_or_none(row.get(column_map.get("tests"))),
            }
        )

    return columns


def read_data_dictionary(dd_source: DDSource, dd_format: str = "ftd_dd") -> list[dict]:
    """
    Read a single data dictionary - a file path (csv/xlsx) or an
    InMemoryDataDictionary - and return one dict per column.

    dd_format selects the column-name mapping to use (see DD_FORMATS in common.py),
    e.g. "ftd_dd", "src_type1", "pipeline_format".
    """
    if isinstance(dd_source, InMemoryDataDictionary):
        suffix = dd_source.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(dd_source.content), dtype="string")
        elif suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(io.BytesIO(dd_source.content))
        elif suffix == ".zip":
            raise ValueError(
                f"'{dd_source.filename}' is a zip archive, not a single data dictionary. "
                "Use --release (generate_models_yml/generate_sources_yml/generate_sql_models) "
                "or pull_release_dd_sources() instead - it expands a *.zip release asset into "
                "its contained *_dd.*/*-dd.* files automatically."
            )
        else:
            raise ValueError(f"Unsupported data dictionary type: {suffix}")
    else:
        df = read_file(Path(dd_source))

    return _extract_columns(df, dd_format)


def build_model_entry(
    table_name: str,
    columns: list[dict],
    *,
    include_tests: bool = True,
) -> tuple[dict, list[tuple[str, str]]]:
    """
    Build one dbt models.yml model entry from columns produced by read_data_dictionary(),
    plus the (doc_id, description) doc blocks for those columns.
    """
    column_entries = []
    doc_blocks = []

    for col in columns:
        col_code = col["formatted_variable_name"]
        doc_id = shorten_identifier(
            normalize_name([table_name, col_code], extension="drop")
        )

        entry = {
            "name": col["variable_name"],
            "description": f'{{{{ doc("{doc_id}") }}}}',
        }

        if include_tests and col.get("tests"):
            entry["tests"] = DbtTesting.format_tests(
                col["tests"], col_code, col.get("enumerations")
            )

        column_entries.append(entry)

        description = (
            col["description"].strip() if col.get("description") else col["variable_name"]
        )
        doc_blocks.append((doc_id, description))

    model = {
        "name": table_name,
        "description": f"Model for {table_name}.",
        "columns": column_entries,
    }

    return model, doc_blocks


def _merge_models(existing_models: list[dict], new_models: list[dict]) -> list[dict]:
    """
    Merge new_models into existing_models, matched by "name".

    Existing models/columns are updated in place and keep their original
    position; models/columns no longer present in new_models are dropped;
    genuinely new ones are appended. This keeps re-running against unchanged
    dds a no-op, and makes changed/added/removed models or columns show up as
    a small, readable diff instead of rewriting the whole file every time.
    """
    new_by_name = {model["name"]: model for model in new_models}

    merged = []
    for model in existing_models:
        match = new_by_name.get(model.get("name"))
        if match is not None:
            merged.append(_merge_model_columns(model, match))

    seen_names = {model.get("name") for model in existing_models}
    for model in new_models:
        if model["name"] not in seen_names:
            merged.append(model)

    return merged


def _merge_model_columns(existing_model: dict, new_model: dict) -> dict:
    """Merge one model's columns, preserving the existing column order."""
    new_columns_by_name = {col["name"]: col for col in new_model.get("columns", [])}

    merged_columns = [
        new_columns_by_name[col["name"]]
        for col in existing_model.get("columns", [])
        if col["name"] in new_columns_by_name
    ]

    existing_names = {col["name"] for col in existing_model.get("columns", [])}
    merged_columns.extend(
        col for col in new_model.get("columns", []) if col["name"] not in existing_names
    )

    return {**new_model, "columns": merged_columns}


def write_models_yml(models: list[dict], output_filepath: Path, *, mode: str = "merge") -> None:
    """
    Write (or merge into) a dbt models.yml file containing the given models.

    In "merge" mode, existing models/columns are matched by name and updated
    in place, rather than the file being rewritten from scratch: unchanged
    entries keep their position and content, changed ones update in place,
    new ones are appended, and ones no longer backed by a dd are dropped.
    """
    output_filepath = Path(output_filepath)

    if mode == "merge" and output_filepath.exists():
        existing = read_file(output_filepath) or {}
        models = _merge_models(existing.get("models") or [], models)
        mode = "overwrite"

    write_file(output_filepath, {"models": models}, mode=mode)


def write_column_descriptions(doc_blocks: list[tuple[str, str]], output_filepath: Path) -> None:
    """Append new `{% docs %}` blocks to a column-descriptions .md file, skipping ids that already exist."""
    output_filepath = Path(output_filepath)
    output_filepath.parent.mkdir(parents=True, exist_ok=True)
    if not output_filepath.exists():
        output_filepath.touch()

    existing = output_filepath.read_text(encoding="utf-8").rstrip()
    existing_ids = set(re.findall(r"\{%\s*docs\s+([\w\d_]+)\s*%\}", existing))

    new_blocks = [
        f"{{% docs {doc_id} %}}\n{description}\n{{% enddocs %}}"
        for doc_id, description in doc_blocks
        if doc_id not in existing_ids
    ]

    if new_blocks:
        content = (
            existing + "\n\n" + "\n\n".join(new_blocks) if existing else "\n\n".join(new_blocks)
        )
        output_filepath.write_text(content, encoding="utf-8")


def generate_models_yml(
    dd_filepaths: DDSource | Iterable[DDSource],
    models_yml_output: Path,
    *,
    table_names: dict[str, str] | None = None,
    table_prefix: str | None = None,
    dd_format: str = "ftd_dd",
    docs_output: Path | None = None,
    include_tests: bool = True,
    mode: str = "merge",
    version_log: Path | None = None,
) -> None:
    """
    Read any set of data dictionaries - a single file, a list of files, a
    directory, and/or InMemoryDataDictionary sources (e.g. from
    pull_release_dd()) - and write one models.yml (and optional column docs)
    covering all of them in a single call. Local files and in-memory sources
    can be freely mixed in the same call.

    If a directory is given, every "*_dd.*"/"*-dd.*" file in it is included.

    There's no notion of a "stage": call this once per set of models you want
    to build (internal, export, or anything else) by pointing it at whatever
    dd sources belong to that set.

    table_names optionally maps a dd file stem -> dbt model name; any dd file
    not listed defaults to its normalized filename stem. table_prefix, if
    given, is prepended to every resulting table name (e.g. table_prefix
    "inc_access" + table name "accesspolicy" -> "inc_access_accesspolicy").

    version_log, if given, appends one row per model to a CSV at that path
    recording where its data came from (source/version/asset/content hash) -
    but only when that information differs from the last recorded row for
    that model, so re-running against unchanged data doesn't grow the log.
    """
    dd_paths = _resolve_dd_filepaths(dd_filepaths)
    table_names = table_names or {}

    models = []
    all_doc_blocks: list[tuple[str, str]] = []
    version_entries: list[tuple[str, dict]] = []

    for dd_filepath in dd_paths:
        table_name = _resolve_table_name(dd_filepath, table_names, table_prefix)

        columns = read_data_dictionary(dd_filepath, dd_format=dd_format)
        model, doc_blocks = build_model_entry(table_name, columns, include_tests=include_tests)

        models.append(model)
        all_doc_blocks.extend(doc_blocks)
        if version_log:
            version_entries.append((table_name, dd_source_descriptor(dd_filepath)))

    write_models_yml(models, models_yml_output, mode=mode)

    if docs_output:
        write_column_descriptions(all_doc_blocks, docs_output)

    if version_log:
        log_dd_versions(version_log, version_entries)


def generate_models_yml_from_release_asset(
    repository_url: str,
    asset_name: str,
    models_yml_output: Path,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
    table_name: str | None = None,
    table_prefix: str | None = None,
    dd_format: str = "ftd_dd",
    docs_output: Path | None = None,
    include_tests: bool = True,
    mode: str = "merge",
    version_log: Path | None = None,
) -> None:
    """
    Pull one named DD file directly from a GitHub release asset (e.g. a
    "patients_dd.csv" already attached to a release) and write/update its
    models.yml entry - no DD CSV is written to disk.

    Every source repository is expected to publish its DD files directly as
    release assets (the release is the source of truth) - this is the only
    release-pulling path in pipeline-utils, and it's zero-dependency
    (github_release.py, stdlib only, no LinkML/the-caddie required).

    This is a thin convenience wrapper around generate_models_yml(): it pulls
    the asset into memory via pull_release_dd() and passes it through, so
    behavior (merging, version_log, etc.) is identical either way.

    The pulled bytes are cached in memory per (repository_url, asset_name,
    tag), so calling this repeatedly doesn't re-hit the network - pass
    refresh=True to force a fresh pull (e.g. after the asset was re-published
    under the same tag). Pulling a different tag always fetches fresh.
    """
    dd_source = pull_release_dd(repository_url, asset_name, tag=tag, token=token, refresh=refresh)
    table_names = {Path(asset_name).stem: table_name} if table_name else None

    generate_models_yml(
        dd_source,
        models_yml_output,
        table_names=table_names,
        table_prefix=table_prefix,
        dd_format=dd_format,
        docs_output=docs_output,
        include_tests=include_tests,
        mode=mode,
        version_log=version_log,
    )


def _strip_dd_suffix(stem: str) -> str:
    """Drop trailing dd suffix markers so they do not leak into model/table names."""

    return re.sub(r"[_-](?:dd|dictionary)$", "", stem, flags=re.IGNORECASE)


def _resolve_table_name(
    dd_filepath: DDSource,
    table_names: dict[str, str],
    table_prefix: str | None,
) -> str:
    """
    Resolve one dd source's table/model name: an explicit table_names
    override, or its normalized filename stem (with a trailing
    "_dd"/"-dd"/"_dictionary"/"-dictionary" stripped), then
    table_prefix prepended if given.
    """

    stem = dd_filepath.stem if isinstance(dd_filepath, InMemoryDataDictionary) else Path(dd_filepath).stem
    base_name = table_names.get(stem) or normalize_name(
        _strip_dd_suffix(stem), extension="drop"
    )
    if table_prefix:
        return normalize_name([table_prefix, base_name], extension="drop")
    return base_name
