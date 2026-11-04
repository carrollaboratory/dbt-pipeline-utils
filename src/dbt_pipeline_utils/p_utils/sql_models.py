"""
Standalone data-dictionary -> dbt SQL model generation.

Same philosophy as models_yml.py/sources_yml.py: functions take explicit
paths and plain values, with no dependency on a shared study/project config.

Each dd produces one SQL model file, replaced on every run with the current
dd-derived SQL. No separate reference copies are written.
"""

from collections.abc import Iterable
from pathlib import Path
import re

from dbt_pipeline_utils import logger
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


def build_program_projection_sql(
    columns: list[dict], *, program_ref_prefix: str
) -> str:
    """Build a typed projection from the matching program model."""
    column_defs = []
    for col in columns:
        alias = col["formatted_variable_name"]
        data_type = (
            "integer"
            if alias == "study_id"
            else type_mapping.get(col["data_type"], "text")
        )
        column_defs.append(f'{col["src_variable_name"]}::{data_type} as "{alias}"')

    return (
        "{{ config(materialized='table') }}\n"
        "{%- set program_ref = "
        "generate_source_ref_from_current_model("
        f"prefix='{program_ref_prefix}') -%}}\n\n"
        "select\n    "
        + ",\n    ".join(column_defs)
        + "\nfrom {{ program_ref }}"
    )


def build_int_descriptor_sql(
    columns: list[dict], *, dd_stem: str, from_clause: str | None = None
) -> str:
    lines = []
    for col in columns:
        name = col["formatted_variable_name"]
        is_external_id = name == "external_id" or name.endswith("_external_id")
        if name.endswith("_id") and not is_external_id:
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
    - selects every DD column using its original source name
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
    program_ref_prefix: str | None = None,
) -> None:
    """
    Read any set of data dictionaries - a single file, a list of files, a
    directory, and/or InMemoryDataDictionary sources (e.g. from
    pull_release_dd()) - and generate one SQL model per table. Local files
    and in-memory sources can be freely mixed in the same call.

    If a directory is given, every "*_dd.*"/"*-dd.*" file in it is included.

    Each model file (output_dir/<table_name>.sql) is replaced on every run,
    including any manual edits. No separate reference copies are written.
    reference_dir is deprecated and ignored.

    from_clause_template, if given, has the literal substring "{table_name}"
    replaced per dd, e.g. "{{ source('raw_study', '{table_name}') }}".
    "{base_name}" is replaced with the table name without table_prefix, e.g.
    "{{ ref('inc_program_{base_name}') }}" with table_prefix "inc_access"
    -> "{{ ref('inc_program_accesspolicy') }}".
    program_ref_prefix, if given, generates configured program-backed
    projections using generate_source_ref_from_current_model and forces
    study_id to integer.

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
    if program_ref_prefix and (int_descriptors or from_clause_template):
        raise ValueError(
            "program_ref_prefix cannot be combined with int_descriptors or "
            "from_clause_template."
        )
    if reference_dir is not None:
        logger.warning(
            "reference_dir is deprecated and ignored; SQL models are overwritten "
            "in output_dir without reference copies."
        )
    table_names = table_names or {}
    version_entries: list[tuple[str, dict]] = []

    for dd_filepath in _resolve_dd_filepaths(dd_filepaths):
        table_name = _resolve_table_name(dd_filepath, table_names, table_prefix)
        base_name = _resolve_table_name(dd_filepath, table_names, None)

        from_clause = (
            from_clause_template.replace("{table_name}", table_name).replace(
                "{base_name}", base_name
            )
            if from_clause_template
            else None
        )

        columns = read_data_dictionary(dd_filepath, dd_format=dd_format)
        sql = (
            build_program_projection_sql(
                columns, program_ref_prefix=program_ref_prefix
            )
            if program_ref_prefix
            else build_int_descriptor_sql(
                columns,
                dd_stem=dd_filepath.stem if hasattr(dd_filepath, "stem") else Path(dd_filepath).stem,
                from_clause=from_clause,
            )
            if int_descriptors
            else build_select_sql(columns, from_clause=from_clause)
        ) + "\n"

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
    - selects each column using src_variable_name when specified, otherwise
      the original variable_name from the DD
    - casts every value to text
    - aliases every output column to lower-snake
    - includes from {{ source(source_name, table_name) }}

    table_prefix affects the table_name used in source(...).
    sql_file_prefix prefixes the unprefixed DD table name in the generated
    SQL filename, independently of table_prefix.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    table_names = table_names or {}
    version_entries: list[tuple[str, dict]] = []

    for dd_filepath in _resolve_dd_filepaths(dd_filepaths):
        base_table_name = _resolve_table_name(dd_filepath, table_names, None)
        table_name = _resolve_table_name(dd_filepath, table_names, table_prefix)
        columns = read_data_dictionary(
            dd_filepath, dd_format=dd_format, source_fallback_to_original=True
        )
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
            normalize_name([sql_file_prefix, base_table_name], extension="drop")
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
