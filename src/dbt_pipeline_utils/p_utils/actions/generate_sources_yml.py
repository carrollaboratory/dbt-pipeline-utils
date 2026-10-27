"""
CLI: add/update tables in a dbt sources.yml file from any set of data
dictionary files.

Accepts one or more files and/or directories in a single call, e.g.:

    generate_sources_yml \\
        -i data_dictionaries/raw \\
        -o models/staging/sources.yml \\
        -s raw_study_data \\
        --schema raw \\
        -d models/staging/_column_descriptions.md

Run it again with a different set of inputs/outputs for another source block
- no shared study/project config is required.
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.actions._release_args import add_release_arguments, resolve_dd_sources
from dbt_pipeline_utils.p_utils.sources_yml import generate_sources_yml


def main():
    parser = argparse.ArgumentParser(
        description="Add/update tables in a dbt sources.yml file from any set of data dictionary files."
    )
    parser.add_argument(
        "-i", "--dd-filepaths", nargs="+", type=Path, default=[],
        help="One or more data dictionary files and/or directories (csv/xlsx). "
             "Optional if --release is given instead.",
    )
    parser.add_argument(
        "-o", "--sources-yml-output", required=True, type=Path,
        help="Path to the output sources.yml file.",
    )
    parser.add_argument(
        "-s", "--source-name", required=True,
        help="dbt source name (the top-level 'sources: - name:' block these tables are grouped under).",
    )
    parser.add_argument(
        "--schema", required=True,
        help="Database schema for the source block.",
    )
    add_release_arguments(parser)
    parser.add_argument(
        "-p", "--table-prefix", default=None,
        help="Prepended to every table name, e.g. 'inc_access' + 'accesspolicy' -> 'inc_access_accesspolicy'.",
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
        "--version-log", default=None, type=Path,
        help="Path to a CSV log to append a row to per table (source/version/asset/content hash) "
             "whenever that information changes from the last recorded row for that table.",
    )
    args = parser.parse_args()

    generate_sources_yml(
        resolve_dd_sources(args),
        args.sources_yml_output,
        source_name=args.source_name,
        schema=args.schema,
        table_prefix=args.table_prefix,
        dd_format=args.dd_format,
        docs_output=args.docs_output,
        version_log=args.version_log,
    )


if __name__ == "__main__":
    main()

