"""
CLI: generate a dbt models.yml (and optional column docs) from any set of
data dictionary files.

Accepts one or more files and/or directories in a single call - there's no
notion of a "stage"; point it at whatever dd files belong together, e.g.:

    generate_models_yml \\
        -i data_dictionaries/access data_dictionaries/extra_table.csv \\
        -o models/access/includes/__models.yml \\
        -d models/access/includes/_column_descriptions.md \\
        -f ftd_dd

Run it again with a different set of inputs/outputs for another set of
models - no shared study/project config is required.
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.actions._release_args import add_release_arguments, resolve_dd_sources
from dbt_pipeline_utils.p_utils.models_yml import generate_models_yml


def main():
    parser = argparse.ArgumentParser(
        description="Generate a dbt models.yml from any set of data dictionary files."
    )
    parser.add_argument(
        "-i", "--dd-filepaths", nargs="+", type=Path, default=[],
        help="One or more data dictionary files and/or directories (csv/xlsx). "
             "Optional if --release is given instead.",
    )
    parser.add_argument(
        "-o", "--models-yml-output", required=True, type=Path,
        help="Path to the output models.yml file.",
    )
    add_release_arguments(parser)
    parser.add_argument(
        "-p", "--table-prefix", default=None,
        help="Prepended to every model name, e.g. 'inc_access' + 'accesspolicy' -> 'inc_access_accesspolicy'.",
    )
    parser.add_argument(
        "-f", "--dd-format", default="ftd_dd",
        help="Data dictionary column-mapping format (see DD_FORMATS in common.py).",
    )
    parser.add_argument(
        "-d", "--docs-output", default=None, type=Path,
        help="Path to a _column_descriptions.md file to append doc blocks to.",
    )
    parser.add_argument(
        "--no-tests", action="store_true",
        help="Skip generating dbt tests from the data dictionaries' tests column.",
    )
    parser.add_argument(
        "-m", "--mode", default="merge", choices=["create", "overwrite", "merge"],
        help="Write mode for the models.yml file (default: merge).",
    )
    parser.add_argument(
        "--version-log", default=None, type=Path,
        help="Path to a CSV log to append a row to per model (source/version/asset/content hash) "
             "whenever that information changes from the last recorded row for that model.",
    )
    args = parser.parse_args()

    generate_models_yml(
        resolve_dd_sources(args),
        args.models_yml_output,
        table_prefix=args.table_prefix,
        dd_format=args.dd_format,
        docs_output=args.docs_output,
        include_tests=not args.no_tests,
        mode=args.mode,
        version_log=args.version_log,
    )


if __name__ == "__main__":
    main()

