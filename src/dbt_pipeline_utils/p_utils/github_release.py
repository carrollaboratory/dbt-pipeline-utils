"""
Zero-dependency GitHub release asset download (stdlib only).

Every source repository is expected to publish its DD files directly as
named release assets (e.g. "patients_dd.csv" attached to a GitHub release) -
the release is the source of truth. This just pulls those bytes.
"""

import json
import zipfile
from io import BytesIO
from pathlib import Path
import urllib.request
from urllib.parse import quote, urlparse

from dbt_pipeline_utils.p_utils.release_cache import cached_pull


REPOSITORY_PRESETS = {
    "kf-access-model": "https://github.com/carrollaboratory/kf-access-model.git",
    "include-access-model": "https://github.com/include-dcc/include-access-model.git",
    "common-access-model": "https://github.com/include-dcc/common-access-model.git",
    "acr-access-model": "https://github.com/anvilproject/acr-harmonized-data-model.git",
    # Short aliases.
    "kf": "https://github.com/carrollaboratory/kf-access-model.git",
    "include": "https://github.com/include-dcc/include-access-model.git",
    "inc": "https://github.com/include-dcc/include-access-model.git",
    "common": "https://github.com/include-dcc/common-access-model.git",
    "acr": "https://github.com/anvilproject/acr-harmonized-data-model.git",
}


def list_repository_presets() -> dict[str, str]:
    """Return supported repository preset aliases and their URLs."""
    return dict(REPOSITORY_PRESETS)


def resolve_repository_url(repository: str) -> str:
    """
    Resolve a repository argument to a GitHub URL.

    Accepts either a full GitHub URL or one of the built-in presets.
    """
    value = repository.strip()
    if not value:
        raise ValueError("repository must be a non-empty URL or preset alias")

    return REPOSITORY_PRESETS.get(value, value)


def _github_repository_parts(repository_url: str) -> tuple[str, str]:
    repository_url = resolve_repository_url(repository_url)
    parsed = urlparse(repository_url.rstrip("/"))
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise ValueError("repository_url must be a GitHub repository URL")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ValueError(
            "repository_url must look like https://github.com/<owner>/<repository>"
        )

    return parts[0], parts[1].removesuffix(".git")


def _request(url: str, token: str | None = None) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "dbt-pipeline-utils",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return response.read()


def _release_json(
    repository_url: str,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
) -> dict:
    resolved_repository = resolve_repository_url(repository_url)

    def _pull() -> dict:
        owner, repository = _github_repository_parts(resolved_repository)
        release_path = "latest" if tag == "latest" else f"tags/{quote(tag, safe='')}"
        api_url = (
            f"https://api.github.com/repos/{owner}/{repository}/releases/{release_path}"
        )
        return json.loads(_request(api_url, token=token))

    # Cache release metadata in memory so repeated operations in one process
    # (list, resolve, pull) do not re-hit GitHub unless explicitly refreshed.
    return cached_pull(("release-json", resolved_repository, tag), refresh, _pull)


def _release_asset_url(
    repository_url: str,
    asset_name: str,
    *,
    tag: str = "latest",
    token: str | None = None,
) -> str:
    release = _release_json(repository_url, tag=tag, token=token, refresh=False)

    for asset in release.get("assets", []):
        if asset.get("name") == asset_name:
            return asset["browser_download_url"]

    available = ", ".join(asset.get("name", "") for asset in release.get("assets", []))
    raise FileNotFoundError(
        f"Release asset '{asset_name}' was not found in {repository_url}@{tag}. "
        f"Available assets: {available or '(none)'}"
    )


def list_release_assets(
    repository_url: str,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
) -> list[dict]:
    """
    List every asset attached to one release: name, size (bytes), content
    type, and download URL - use this to see what's actually in a release
    before pulling one asset by name.
    """
    release = _release_json(repository_url, tag=tag, token=token, refresh=refresh)

    return [
        {
            "name": asset.get("name"),
            "size": asset.get("size"),
            "content_type": asset.get("content_type"),
            "updated_at": asset.get("updated_at"),
            "url": asset.get("browser_download_url"),
        }
        for asset in release.get("assets", [])
    ]


def pull_release_asset_to_memory(
    repository_url: str,
    asset_name: str,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
) -> bytes:
    """
    Download one named GitHub release asset and return its bytes - nothing
    written to disk.

    The result is cached in memory per (repository_url, asset_name, tag), so
    repeated calls don't re-hit the network. Pass refresh=True to force a
    fresh pull, e.g. if the asset was re-published under the same tag.
    """

    def _pull() -> bytes:
        asset_url = _release_asset_url(repository_url, asset_name, tag=tag, token=token)
        return _request(asset_url, token=token)

    return cached_pull(("asset", repository_url, asset_name, tag), refresh, _pull)


def pull_release_artifact_file_to_path(
    repository_url: str,
    artifact_name: str,
    internal_path: str,
    output_path: str | Path,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
) -> Path:
    """
    Extract one file or directory from a ZIP release artifact to output_path.

    File mode:
    - internal_path can be an exact ZIP member path (recommended), or
        a basename match if that basename is unique within the archive.

    Directory mode:
    - If no file match is found and internal_path resolves to a directory
        prefix within the ZIP, all files under that prefix are copied into
        output_path (treated as a destination directory).
    """
    if not artifact_name.lower().endswith(".zip"):
        raise ValueError(
            "pull_release_artifact_file_to_path only supports .zip artifacts"
        )

    artifact_bytes = pull_release_asset_to_memory(
        repository_url, artifact_name, tag=tag, token=token, refresh=refresh
    )

    internal = internal_path.strip().lstrip("/").replace("\\", "/")
    if not internal:
        raise ValueError("internal_path must be a non-empty path inside the ZIP")

    with zipfile.ZipFile(BytesIO(artifact_bytes)) as archive:
        members = [info.filename for info in archive.infolist() if not info.is_dir()]
        selected_member: str | None = None

        if internal in members:
            selected_member = internal
        else:
            suffix_matches = [
                name
                for name in members
                if name == internal
                or name.endswith("/" + internal)
                or Path(name).name == internal
            ]
            if len(suffix_matches) == 1:
                selected_member = suffix_matches[0]
            elif len(suffix_matches) > 1:
                matches = ", ".join(sorted(suffix_matches))
                raise FileNotFoundError(
                    f"Multiple files in {artifact_name} matched '{internal_path}'. "
                    f"Use an exact internal path. Matches: {matches}"
                )

        if selected_member:
            payload = archive.read(selected_member)
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            return destination

        # Directory extraction mode.
        normalized = internal.rstrip("/")
        prefix = f"{normalized}/"
        dir_members = [name for name in members if name.startswith(prefix)]

        if not dir_members:
            slash_marker = f"/{normalized}/"
            suffix_prefixes = {
                name[: name.find(slash_marker) + len(slash_marker)]
                for name in members
                if slash_marker in name
            }
            if len(suffix_prefixes) == 1:
                matched_prefix = next(iter(suffix_prefixes))
                dir_members = [
                    name for name in members if name.startswith(matched_prefix)
                ]
                prefix = matched_prefix
            elif len(suffix_prefixes) > 1:
                matches = ", ".join(sorted(suffix_prefixes))
                raise FileNotFoundError(
                    f"Multiple directories in {artifact_name} matched '{internal_path}'. "
                    f"Use an exact internal path. Matches: {matches}"
                )

        if not dir_members:
            preview = ", ".join(sorted(members)[:20])
            if len(members) > 20:
                preview += ", ..."
            raise FileNotFoundError(
                f"Path '{internal_path}' not found inside {artifact_name} from "
                f"{repository_url}@{tag}. Available files: {preview or '(none)'}"
            )

        destination_dir = Path(output_path)
        if destination_dir.exists() and destination_dir.is_file():
            raise ValueError(
                f"output_path '{destination_dir}' is a file, but directory extraction "
                "was requested"
            )

        copied_files = 0
        for member in dir_members:
            relative = member.removeprefix(prefix).lstrip("/")
            if not relative:
                continue
            target = destination_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
            copied_files += 1

        if copied_files == 0:
            raise FileNotFoundError(
                f"Directory '{internal_path}' matched no files inside {artifact_name}"
            )

        return destination_dir
