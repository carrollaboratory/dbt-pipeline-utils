"""
CLI: extract one file or directory from a ZIP release artifact to a chosen
local path.

The repository can be either a full GitHub URL or a preset alias:
- kf-access-model / kf
- include-access-model / include
- common-access-model / common

Example:

    extract_release_artifact_file \
        kf \
        project-artifacts.zip \
        data_dictionaries/patients_dd.csv \
        ./tmp/patients_dd.csv

    extract_release_artifact_file \
        kf \
        project-artifacts.zip \
        project/data-dictionary \
        ./tmp/data-dictionary
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.github_release import (
    list_repository_presets,
    pull_release_artifact_file_to_path,
    resolve_repository_url,
)


def _preset_help_text() -> str:
    presets = list_repository_presets()
    names = sorted({name for name in presets if len(name) > 2})
    return ", ".join(names)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract one file or directory from a ZIP GitHub release artifact to a "
            "local path. "
            "Repository may be a full URL or a preset alias."
        )
    )
    parser.add_argument(
        "repository",
        help=(
            "GitHub repository URL (https://github.com/<owner>/<repo>) or preset alias "
            f"({_preset_help_text()})."
        ),
    )
    parser.add_argument(
        "artifact_name",
        help="ZIP release asset name, e.g. project-artifacts.zip.",
    )
    parser.add_argument(
        "internal_path",
        help=(
            "Path inside the ZIP artifact. If it resolves to a file, that file is "
            "copied. If it resolves to a directory prefix, all files under that "
            "prefix are copied."
        ),
    )
    parser.add_argument(
        "output_path",
        type=Path,
        help=(
            "Destination path on local disk. Use a file path for file extraction or "
            "a directory path for directory extraction."
        ),
    )
    parser.add_argument(
        "-t",
        "--tag",
        default="latest",
        help="Release tag to pull (default: latest).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub token, for private repositories.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force a fresh pull instead of using in-memory cache.",
    )

    args = parser.parse_args()

    destination = pull_release_artifact_file_to_path(
        resolve_repository_url(args.repository),
        args.artifact_name,
        args.internal_path,
        args.output_path,
        tag=args.tag,
        token=args.token,
        refresh=args.refresh,
    )
    print(destination)


if __name__ == "__main__":
    main()
