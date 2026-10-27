"""
CLI: generate src dbt SQL models from DD inputs.

For each data dictionary, writes one SQL model that:
- includes config(materialized='table')
- selects every DD column
- casts every selected value to text
- aliases every output column to lower-snake
- uses source(source_name, table_name) in the from clause
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.actions._release_args import add_release_arguments, resolve_dd_sources
from dbt_pipeline_utils.p_utils.sql_models import generate_src_models


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate one src SQL model per DD with source(...), lower-snake aliases, "
            "and cast-all-to-text behavior."
        )
    )
    parser.add_argument(
        "-i", "--dd-filepaths", nargs="+", type=Path, default=[],
        help="One or more data dictionary files and/or directories (csv/xlsx). Optional if --release is given.",
    )
    parser.add_argument(
        "-o", "--output-dir", required=True, type=Path,
        help="Directory where src model .sql files are written.",
    )
    parser.add_argument(
        "-s", "--source-name", required=True,
        help="dbt source name used in from {{ source('<source_name>', '<table_name>') }}.",
    )
    add_release_arguments(parser)
    parser.add_argument(
        "-p", "--table-prefix", default=None,
        help="Prepended to source table names used in source(...).",
    )
    parser.add_argument(
        "--sql-file-prefix", default=None,
        help="Prepended only to generated SQL filenames; does not affect source(...).",
    )
    parser.add_argument(
        "-f", "--dd-format", default="ftd_dd",
        help="Data dictionary column-mapping format (see DD_FORMATS in common.py).",
    )
    parser.add_argument(
        "--materialized", default="table",
        help="dbt materialization for config(materialized=...), default: table.",
    )
    parser.add_argument(
        "--version-log", default=None, type=Path,
        help=(
            "Path to a CSV log to append one row per model (source/version/asset/content hash) "
            "when that information changes."
        ),
    )
    args = parser.parse_args()

    generate_src_models(
        resolve_dd_sources(args),
        args.output_dir,
        source_name=args.source_name,
        table_prefix=args.table_prefix,
        sql_file_prefix=args.sql_file_prefix,
        dd_format=args.dd_format,
        materialized=args.materialized,
        version_log=args.version_log,
    )


if __name__ == "__main__":
    main()
