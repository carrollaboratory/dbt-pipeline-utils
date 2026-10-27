"""
Shared --release CLI plumbing: lets any of the generate_* CLIs pull one or
more GitHub release assets into memory as additional dd sources, combined
with (or instead of) local -i files/directories. A "*.zip" release asset is
automatically expanded into its contained "*_dd.*"/"*-dd.*" files.
"""

import argparse

from dbt_pipeline_utils.p_utils.dd_sources import pull_release_dd_sources

def add_release_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--release", nargs=2, action="append", metavar=("REPO_URL", "ASSET_NAME"),
        help="Pull one release asset into memory as an additional dd source (repeatable). "
             "Combine with -i for local files, or omit -i entirely to use release assets only.",
    )
    parser.add_argument(
        "--release-tag", default="latest",
        help="Release tag to pull --release assets from (default: latest).",
    )
    parser.add_argument(
        "--release-token", default=None,
        help="GitHub token, for private repositories.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force a fresh pull of --release assets instead of using the in-memory "
             "cache from an earlier call in this process.",
    )


def resolve_dd_sources(args: argparse.Namespace) -> list:
    """Combine -i dd_filepaths (if any) with pulled --release assets into one source list."""
    sources = list(args.dd_filepaths or [])

    for repo_url, asset_name in args.release or []:
        sources.extend(
            pull_release_dd_sources(
                repo_url,
                asset_name,
                tag=args.release_tag,
                token=args.release_token,
                refresh=args.refresh,
            )
        )

    if not sources:
        raise SystemExit("Provide at least one input via -i/--dd-filepaths or --release.")

    return sources
