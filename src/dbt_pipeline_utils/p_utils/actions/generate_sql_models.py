"""
CLI: generate dbt SQL models
from any set of data dictionary files.

Accepts one or more files and/or directories in a single call, e.g.:

    generate_sql_models \\
        -i data_dictionaries/int \\
        -o models/int \\
        --from-clause-template "{{ source('raw_study', '{table_name}') }}"

Each model file (models/int/<table>.sql) is replaced on every run, including
any manual edits. No separate reference copies are written.
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.actions._release_args import add_release_arguments, resolve_dd_sources
from dbt_pipeline_utils.p_utils.sql_models import generate_sql_models


def main():
    parser = argparse.ArgumentParser(
        description="Generate dbt SQL models from data dictionaries, overwriting existing SQL files."
    )
    parser.add_argument(
        "-i", "--dd-filepaths", nargs="+", type=Path, default=[],
        help="One or more data dictionary files and/or directories (csv/xlsx). "
             "Optional if --release is given instead.",
    )
    parser.add_argument(
        "-o", "--output-dir", required=True, type=Path,
        help="Directory for *.sql model files. Existing files, including manual edits, are overwritten.",
    )
    add_release_arguments(parser)
    parser.add_argument(
        "-p", "--table-prefix", default=None,
        help="Prepended to every table name, e.g. 'inc_access' + 'accesspolicy' -> 'inc_access_accesspolicy.sql'.",
    )
    parser.add_argument(
        "-f", "--dd-format", default="ftd_dd",
        help="Data dictionary column-mapping format (see DD_FORMATS in common.py).",
    )
    parser.add_argument(
        "--from-clause-template", default=None,
        help="Literal \"{table_name}\" is replaced per dd, e.g. \"{{ source('raw_study', '{table_name}') }}\". "
             "\"{base_name}\" is the table name without --table-prefix, e.g. \"{{ ref('inc_program_{base_name}') }}\".",
    )
    parser.add_argument(
        "--reference-dir", default=None, type=Path,
        help="Deprecated and ignored. No reference copies are generated.",
    )
    parser.add_argument(
        "--int-descriptors",
        action="store_true",
        help="Create zero-row int table SQL with a null descriptor and commented-out ID columns.",
    )
    parser.add_argument(
        "--version-log",
        default=None,
        type=Path,
        help="Path to a CSV log to append a row to per table (source/version/asset/content hash) "
        "whenever that information changes from the last recorded row for that table.",
    )
    args = parser.parse_args()

    generate_sql_models(
        resolve_dd_sources(args),
        args.output_dir,
        table_prefix=args.table_prefix,
        dd_format=args.dd_format,
        from_clause_template=args.from_clause_template,
        reference_dir=args.reference_dir,
        version_log=args.version_log,
        int_descriptors=args.int_descriptors,
    )


if __name__ == "__main__":
    main()
