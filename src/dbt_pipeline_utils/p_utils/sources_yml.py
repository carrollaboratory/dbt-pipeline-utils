"""
Standalone data-dictionary -> dbt sources.yml generation.

Same philosophy as models_yml.py: every function takes explicit file paths
and plain values, with no dependency on StudyConfig/PipelineObject/StructureBC.
Compose these from a bash script (e.g. one call per raw table) rather than a
shared project config.
"""

from collections.abc import Iterable
from pathlib import Path

import yaml

from dbt_pipeline_utils.p_utils.files import normalize_name, shorten_identifier
from dbt_pipeline_utils.p_utils.models_yml import (
    DDSource,
    _merge_models,
    _resolve_dd_filepaths,
    _resolve_table_name,
    dd_source_descriptor,
    log_dd_versions,
    read_data_dictionary,
    write_column_descriptions,
)


def build_source_table_entry(table_name: str, columns: list[dict]) -> tuple[dict, list[tuple[str, str]]]:
    """
    Build one sources.yml table entry from columns produced by read_data_dictionary(),
    plus the (doc_id, description) doc blocks for those columns.

    Sources describe raw data, not modeled data, so no dbt tests are attached.
    """
    column_entries = []
    doc_blocks = []

    for col in columns:
        col_code = col["formatted_variable_name"]
        doc_id = shorten_identifier(
            normalize_name([table_name, col_code], extension="drop")
        )

        column_entries.append(
            {
                "name": col["variable_name"],
                "description": f'{{{{ doc("{doc_id}") }}}}',
            }
        )

        description = (
            col["description"].strip() if col.get("description") else col["variable_name"]
        )
        doc_blocks.append((doc_id, description))

    table = {
        "name": table_name,
        "description": f"Source table for {table_name}.",
        "columns": column_entries,
    }

    return table, doc_blocks


def write_sources_yml(source_name: str, schema: str, tables: list[dict], output_filepath: Path) -> None:
    """
    Merge the given tables into output_filepath's sources.yml, under the
    source block named source_name (creating it with the given schema if
    needed).

    Tables/columns are matched by name and updated in place - same merge
    semantics as write_models_yml - so unchanged tables/entries keep their
    position and content, changed ones update in place, new ones are
    appended, and ones no longer backed by a dd are dropped.
    """
    output_filepath = Path(output_filepath)

    existing = {}
    if output_filepath.exists():
        existing = yaml.safe_load(output_filepath.read_text(encoding="utf-8")) or {}

    sources = existing.setdefault("sources", [])

    source_block = next((s for s in sources if s.get("name") == source_name), None)
    if source_block is None:
        source_block = {"name": source_name, "schema": schema, "tables": []}
        sources.append(source_block)
    else:
        source_block["schema"] = schema

    source_block["tables"] = _merge_models(source_block.get("tables") or [], tables)

    output_filepath.parent.mkdir(parents=True, exist_ok=True)
    output_filepath.write_text(
        yaml.safe_dump(existing, sort_keys=False, default_flow_style=False, indent=2),
        encoding="utf-8",
    )


def generate_sources_yml(
    dd_filepaths: DDSource | Iterable[DDSource],
    sources_yml_output: Path,
    *,
    source_name: str,
    schema: str,
    table_names: dict[str, str] | None = None,
    table_prefix: str | None = None,
    dd_format: str = "ftd_dd",
    docs_output: Path | None = None,
    version_log: Path | None = None,
) -> None:
    """
    Read any set of data dictionaries - a single file, a list of files, a
    directory, and/or InMemoryDataDictionary sources (e.g. from
    pull_release_dd()) - and write/update their tables under one
    source/schema block of a dbt sources.yml file in a single call. Local
    files and in-memory sources can be freely mixed in the same call.

    If a directory is given, every "*_dd.*"/"*-dd.*" file in it is included.

    table_names optionally maps a dd file stem -> table name; any dd file not
    listed defaults to its normalized filename stem (with a trailing
    "_dd"/"-dd" stripped). table_prefix, if given, is prepended to every
    resulting table name (e.g. table_prefix "inc_access" + table name
    "accesspolicy" -> "inc_access_accesspolicy").

    version_log, if given, appends one row per table to a CSV at that path
    recording where its data came from (source/version/asset/content hash) -
    but only when that information differs from the last recorded row for
    that table, so re-running against unchanged data doesn't grow the log.
    """
    dd_paths = _resolve_dd_filepaths(dd_filepaths)
    table_names = table_names or {}

    tables = []
    all_doc_blocks: list[tuple[str, str]] = []
    version_entries: list[tuple[str, dict]] = []

    for dd_filepath in dd_paths:
        table_name = _resolve_table_name(dd_filepath, table_names, table_prefix)

        columns = read_data_dictionary(dd_filepath, dd_format=dd_format)
        table, doc_blocks = build_source_table_entry(table_name, columns)

        tables.append(table)
        all_doc_blocks.extend(doc_blocks)
        if version_log:
            version_entries.append((table_name, dd_source_descriptor(dd_filepath)))

    write_sources_yml(source_name, schema, tables, sources_yml_output)

    if all_doc_blocks and docs_output:
        write_column_descriptions(all_doc_blocks, docs_output)

    if version_log:
        log_dd_versions(version_log, version_entries)
