"""
CLI: list every asset attached to one GitHub release - use this to see
what's actually in a release before pulling a specific dd asset by name.

    list_release_assets https://github.com/<owner>/<repo> [-t <tag>] [--token <token>]
"""

import argparse

from dbt_pipeline_utils.p_utils.github_release import (
    list_release_assets,
    list_repository_presets,
    resolve_repository_url,
)


def _preset_help_text() -> str:
    presets = list_repository_presets()
    aliases = sorted(
        name
        for name in presets
        if name not in {"kf-access-model", "include-access-model", "common-access-model"}
    )
    return ", ".join(aliases)


def main():
    parser = argparse.ArgumentParser(
        description="List every asset attached to one GitHub release."
    )
    parser.add_argument(
        "repository_url",
        help=(
            "GitHub repository URL, e.g. https://github.com/<owner>/<repo>, "
            f"or preset alias ({_preset_help_text()})."
        ),
    )
    parser.add_argument(
        "-t", "--tag", default="latest",
        help="Release tag to inspect (default: latest).",
    )
    parser.add_argument(
        "--token", default=None,
        help="GitHub token, for private repositories.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force a fresh metadata pull instead of in-memory cache.",
    )
    args = parser.parse_args()

    repository_url = resolve_repository_url(args.repository_url)
    assets = list_release_assets(
        repository_url,
        tag=args.tag,
        token=args.token,
        refresh=args.refresh,
    )

    if not assets:
        print(f"No assets found in {args.repository_url}@{args.tag}.")
        return

    for asset in assets:
        print(f"{asset['name']}\t{asset['size']} bytes\t{asset['content_type']}\t{asset['updated_at']}")


if __name__ == "__main__":
    main()
