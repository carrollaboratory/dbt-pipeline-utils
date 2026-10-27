"""
Standalone data-dictionary -> dbt SQL model generation.

Same philosophy as models_yml.py/sources_yml.py: functions take explicit
paths and plain values, with no dependency on a shared study/project config.

Each dd produces one hand-editable SQL model file. That file is created once
and never overwritten, since data devs harmonize it by hand afterwards.
Alongside it, a "<table>_generated.sql" reference file is always (re)written
with the current dd-derived SQL, so devs can diff the two to see exactly
what's changed in the dd since the model was last harmonized:

    diff models/int/patients.sql models/int/patients_generated.sql
"""

from collections.abc import Iterable
from pathlib import Path
import re

from dbt_pipeline_utils.p_utils.common import type_mapping
from dbt_pipeline_utils.p_utils.files import normalize_name, write_file
from dbt_pipeline_utils.p_utils.models_yml import (
    DDSource,
    _resolve_dd_filepaths,
    _resolve_table_name,
    dd_source_descriptor,
    log_dd_versions,
    read_data_dictionary,
)


def _quote_identifier(name: str) -> str:
    """Return a safely SQL-quoted identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def build_select_sql(columns: list[dict], *, from_clause: str | None = None) -> str:
    """
    Build a plain 'select ... [from ...]' SQL body from data-dictionary
    columns, casting each column to its warehouse type and aliasing it to its
    normalized name.

    from_clause, if given, is appended as-is, e.g. "{{ source('raw', 'patients') }}"
    or "{{ ref('stg_patients') }}".
    """
    column_defs = [
        f'{col["src_variable_name"]}::{type_mapping.get(col["data_type"], "text")} '
        f'as "{col["formatted_variable_name"]}"'
        for col in columns
    ]

    sql = "select\n    " + ",\n    ".join(column_defs)
    if from_clause:
        sql += f"\nfrom {from_clause}"

    return sql


def build_int_descriptor_sql(
    columns: list[dict], *, dd_stem: str, from_clause: str | None = None
) -> str:
    lines = []
    for col in columns:
        name = col["formatted_variable_name"]
        if name.endswith("_id"):
            lines.append(f"    -- null::text as {name}, -- Global ID generated in the stb model")
        else:
            lines.append(f"    null::text as {name},")

    descriptor_name = _table_base_from_stem(
        re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", dd_stem)
    )
    lines.append(f"    null::text as {descriptor_name}_descriptor")
    sql = "{{ config(materialized='table') }}\n\nselect\n" + "\n".join(lines)
    if from_clause:
        sql += f"\nfrom {from_clause}"
    return sql + "\nwhere false"


def build_src_select_sql(
    columns: list[dict],
    *,
    source_name: str,
    table_name: str,
    materialized: str = "table",
) -> str:
    """
    Build a src model SQL body that:
    - includes dbt config(materialized=...)
    - selects every DD column
    - casts every selected value to text (string)
    - aliases every output column to lower-snake
    - reads from source(source_name, table_name)
    """
    lines = []
    for col in columns:
        source_col = _quote_identifier(col["src_variable_name"])
        alias = col["formatted_variable_name"]
        lines.append(f"{source_col}::text as {alias}")

    return (
        f"{{{{ config(materialized='{materialized}') }}}}\n\n"
        "select\n    "
        + ",\n    ".join(lines)
        + f"\nfrom {{{{ source('{source_name}', '{table_name}') }}}}"
    )


def generate_sql_models(
    dd_filepaths: DDSource | Iterable[DDSource],
    output_dir: Path,
    *,
    dd_format: str = "ftd_dd",
    from_clause_template: str | None = None,
    reference_dir: Path | None = None,
    table_names: dict[str, str] | None = None,
    table_prefix: str | None = None,
    version_log: Path | None = None,
    int_descriptors: bool = False,
) -> None:
    """
    Read any set of data dictionaries - a single file, a list of files, a
    directory, and/or InMemoryDataDictionary sources (e.g. from
    pull_release_dd()) - and generate one SQL model per table. Local files
    and in-memory sources can be freely mixed in the same call.

    If a directory is given, every "*_dd.*"/"*-dd.*" file in it is included.

    Each model file (output_dir/<table_name>.sql) is created if missing and
    never overwritten once it exists, since data devs hand-edit it to
    harmonize the data. A "<table_name>_generated.sql" file next to it (or
    under reference_dir, if given) is always (re)written with the current
    dd-derived SQL - diff the two to see exactly what's changed in the dd
    since the model was last harmonized.

    from_clause_template, if given, has the literal substring "{table_name}"
    replaced per dd, e.g. "{{ source('raw_study', '{table_name}') }}".

    table_names optionally maps a dd file stem -> table name; any dd file not
    listed defaults to its normalized filename stem (with a trailing
    "_dd"/"-dd" stripped). table_prefix, if given, is prepended to every
    resulting table name (e.g. table_prefix "inc_access" + table name
    "accesspolicy" -> "inc_access_accesspolicy", so the model is written to
    "inc_access_accesspolicy.sql").

    version_log, if given, appends one row per table to a CSV at that path
    recording where its data came from (source/version/asset/content hash) -
    but only when that information differs from the last recorded row for
    that table, so re-running against unchanged data doesn't grow the log.
    """
    output_dir = Path(output_dir)
    reference_dir = Path(reference_dir) if reference_dir else output_dir
    table_names = table_names or {}
    version_entries: list[tuple[str, dict]] = []

    for dd_filepath in _resolve_dd_filepaths(dd_filepaths):
        table_name = _resolve_table_name(dd_filepath, table_names, table_prefix)

        from_clause = (
            from_clause_template.replace("{table_name}", table_name)
            if from_clause_template
            else None
        )

        columns = read_data_dictionary(dd_filepath, dd_format=dd_format)
        sql = (
            build_int_descriptor_sql(
                columns,
                dd_stem=dd_filepath.stem if hasattr(dd_filepath, "stem") else Path(dd_filepath).stem,
                from_clause=from_clause,
            )
            if int_descriptors
            else build_select_sql(columns, from_clause=from_clause)
        ) + "\n"

        reference_filepath = reference_dir / f"{table_name}_generated.sql"
        reference_filepath.parent.mkdir(parents=True, exist_ok=True)
        reference_filepath.write_text(sql, encoding="utf-8")

        # write_file() never overwrites an existing *.sql file - the dev's
        # harmonized model is left untouched once it exists.
        write_file(output_dir / f"{table_name}.sql", sql)

        if version_log:
            version_entries.append((table_name, dd_source_descriptor(dd_filepath)))

    if version_log:
        log_dd_versions(version_log, version_entries)


def generate_src_models(
    dd_filepaths: DDSource | Iterable[DDSource],
    output_dir: Path,
    *,
    source_name: str,
    dd_format: str = "ftd_dd",
    table_names: dict[str, str] | None = None,
    table_prefix: str | None = None,
    sql_file_prefix: str | None = None,
    materialized: str = "table",
    version_log: Path | None = None,
) -> None:
    """
    Generate one src SQL model per DD source.

    Each model:
    - includes config(materialized='table')
    - selects every DD column
    - casts every value to text
    - aliases every output column to lower-snake
    - includes from {{ source(source_name, table_name) }}

    table_prefix affects the table_name used in source(...).
    sql_file_prefix affects only the generated SQL filename.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    table_names = table_names or {}
    version_entries: list[tuple[str, dict]] = []

    for dd_filepath in _resolve_dd_filepaths(dd_filepaths):
        table_name = _resolve_table_name(dd_filepath, table_names, table_prefix)
        columns = read_data_dictionary(dd_filepath, dd_format=dd_format)
        sql = (
            build_src_select_sql(
                columns,
                source_name=source_name,
                table_name=table_name,
                materialized=materialized,
            )
            + "\n"
        )

        model_name = (
            normalize_name([sql_file_prefix, table_name], extension="drop")
            if sql_file_prefix
            else table_name
        )
        model_path = output_dir / f"{model_name}.sql"
        model_path.write_text(sql, encoding="utf-8")

        if version_log:
            version_entries.append((model_name, dd_source_descriptor(dd_filepath)))

    if version_log:
        log_dd_versions(version_log, version_entries)


def _table_base_from_stem(stem: str) -> str:
    stem = re.sub(r"[_-](?:dd|dictionary)$", "", stem, flags=re.IGNORECASE)
    return normalize_name(stem, extension="drop")


def generate_stb_union_models(
    dd_filepaths: DDSource | Iterable[DDSource],
    output_dir: Path,
    *,
    studies_var: str = "inc_studies",
    model_prefix: str = "combined",
) -> int:
    """
    Generate one STB union model file per DD source.

    Each generated file contains:
    {{ config(materialized='table') }}

    {{ combined_union_from_current_model(studies_var='...') }}

    Sources may be local files/directories and/or in-memory release assets.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    seen_model_names: set[str] = set()

    for dd_filepath in _resolve_dd_filepaths(dd_filepaths):
        stem = dd_filepath.stem if hasattr(dd_filepath, "stem") else Path(dd_filepath).stem
        base_name = _table_base_from_stem(stem)
        model_name = (
            normalize_name([model_prefix, base_name], extension="drop")
            if model_prefix
            else base_name
        )

        if model_name in seen_model_names:
            continue
        seen_model_names.add(model_name)

        model_path = output_dir / f"{model_name}.sql"
        model_sql = (
            "{{ config(materialized='table') }}\n\n"
            f"{{{{ combined_union_from_current_model(studies_var='{studies_var}') }}}}\n"
        )
        model_path.write_text(model_sql, encoding="utf-8")
        written += 1

    return written
