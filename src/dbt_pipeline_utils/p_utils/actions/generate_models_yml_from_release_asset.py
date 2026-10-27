"""
CLI: generate a dbt models.yml directly from one named GitHub release asset
(e.g. a "patients_dd.csv" already published on a release), without writing
any DD CSV to disk.

Every source repository is expected to publish its DD files directly as
release assets - the release is the source of truth. Zero-dependency: only
needs pipeline-utils itself.

    generate_models_yml_from_release_asset \\
        https://github.com/<owner>/<repo> \\
        patients_dd.csv \\
        -o models/access/includes/__models.yml \\
        -p inc_access \\
        -d models/access/includes/_column_descriptions.md

Each invocation is independent - no shared study/project config is required.
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.github_release import resolve_repository_url
from dbt_pipeline_utils.p_utils.models_yml import generate_models_yml_from_release_asset


def main():
    parser = argparse.ArgumentParser(
        description="Generate a dbt models.yml directly from one named GitHub release asset, in memory."
    )
    parser.add_argument(
        "repository_url",
        help="GitHub repository URL to pull the release from, e.g. https://github.com/<owner>/<repo>.",
    )
    parser.add_argument(
        "asset_name",
        help="Exact filename of the release asset to pull, e.g. patients_dd.csv.",
    )
    parser.add_argument(
        "-o", "--models-yml-output", required=True, type=Path,
        help="Path to the output models.yml file.",
    )
    parser.add_argument(
        "-t", "--tag", default="latest",
        help="Release tag to pull (default: latest).",
    )
    parser.add_argument(
        "--token", default=None,
        help="GitHub token, for private repositories.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force a fresh pull instead of using the in-memory cache from an earlier call in this process.",
    )
    parser.add_argument(
        "-n", "--table-name", default=None,
        help="dbt model name. Defaults to the normalized asset filename.",
    )
    parser.add_argument(
        "-p", "--table-prefix", default=None,
        help="Prepended to the model name, e.g. 'inc_access' + 'accesspolicy' -> 'inc_access_accesspolicy'.",
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
        help="Skip generating dbt tests from the data dictionary's tests column.",
    )
    parser.add_argument(
        "-m", "--mode", default="merge", choices=["create", "overwrite", "merge"],
        help="Write mode for the models.yml file (default: merge).",
    )
    parser.add_argument(
        "--version-log", default=None, type=Path,
        help="Path to a CSV log to append a row to for this model (source/version/asset/content hash) "
             "whenever that information changes from the last recorded row for that model.",
    )
    args = parser.parse_args()

    generate_models_yml_from_release_asset(
        resolve_repository_url(args.repository_url),
        args.asset_name,
        args.models_yml_output,
        tag=args.tag,
        token=args.token,
        refresh=args.refresh,
        table_name=args.table_name,
        table_prefix=args.table_prefix,
        dd_format=args.dd_format,
        docs_output=args.docs_output,
        include_tests=not args.no_tests,
        mode=args.mode,
        version_log=args.version_log,
    )


if __name__ == "__main__":
    main()
