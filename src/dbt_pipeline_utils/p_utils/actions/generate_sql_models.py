"""
CLI: generate dbt SQL models (plus always-current, diffable reference copies)
from any set of data dictionary files.

Accepts one or more files and/or directories in a single call, e.g.:

    generate_sql_models \\
        -i data_dictionaries/int \\
        -o models/int \\
        --from-clause-template "{{ source('raw_study', '{table_name}') }}"

Each model file (models/int/<table>.sql) is created once and never
overwritten - data devs hand-edit it to harmonize the data. A
models/int/<table>_generated.sql file is always refreshed with the current
dd-derived SQL, so a dev can run:

    diff models/int/<table>_generated.sql models/int/<table>.sql

to see exactly what's changed in the dd since they last harmonized the model.
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.actions._release_args import add_release_arguments, resolve_dd_sources
from dbt_pipeline_utils.p_utils.sql_models import generate_sql_models


def main():
    parser = argparse.ArgumentParser(
        description="Generate dbt SQL models (plus diffable reference copies) from any set of data dictionary files."
    )
    parser.add_argument(
        "-i", "--dd-filepaths", nargs="+", type=Path, default=[],
        help="One or more data dictionary files and/or directories (csv/xlsx). "
             "Optional if --release is given instead.",
    )
    parser.add_argument(
        "-o", "--output-dir", required=True, type=Path,
        help="Directory for the dev-owned, hand-edited *.sql model files.",
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
        help="Literal \"{table_name}\" is replaced per dd, e.g. \"{{ source('raw_study', '{table_name}') }}\".",
    )
    parser.add_argument(
        "--reference-dir", default=None, type=Path,
        help="Directory for the always-current *_generated.sql reference files (defaults to --output-dir).",
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
