"""
Shared data-dictionary source handling.

A "dd source" passed to generate_models_yml/generate_sources_yml/
generate_sql_models can be a local file path, a directory of files, or an
InMemoryDataDictionary (e.g. pulled from a GitHub release asset via
pull_release_dd()) - any mix of these can be passed in the same call.
"""

from __future__ import annotations

import csv
import hashlib
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class InMemoryDataDictionary:
    """A data dictionary held in memory instead of read from a file on disk."""

    filename: str
    content: bytes
    source: str = "in-memory"
    version: str = ""

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def suffix(self) -> str:
        return Path(self.filename).suffix


DDSource = Path | str | InMemoryDataDictionary


def _is_dd_filename(filename: str) -> bool:
    """Return True if filename matches supported DD suffix conventions."""
    lower = filename.lower()
    return lower.endswith(
        (
            "_dd.csv",
            "-dd.csv",
            "_dd.xlsx",
            "-dd.xlsx",
            "_dictionary.csv",
            "-dictionary.csv",
            "_dictionary.xlsx",
            "-dictionary.xlsx",
        )
    )


def pull_release_dd(
    repository_url: str,
    asset_name: str,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
) -> InMemoryDataDictionary:
    """
    Pull one named GitHub release asset into memory as a dd source, usable
    directly in generate_models_yml/generate_sources_yml/generate_sql_models
    alongside (or instead of) local CSV/XLSX files - no file is written to
    disk.

    Cached in memory per (repository_url, asset_name, tag); pass refresh=True
    to force a fresh pull.
    """
    from dbt_pipeline_utils.p_utils.github_release import pull_release_asset_to_memory

    content = pull_release_asset_to_memory(
        repository_url, asset_name, tag=tag, token=token, refresh=refresh
    )
    return InMemoryDataDictionary(
        filename=asset_name, content=content, source=repository_url, version=tag
    )


def pull_release_dd_sources(
    repository_url: str,
    asset_name: str,
    *,
    tag: str = "latest",
    token: str | None = None,
    refresh: bool = False,
) -> list[InMemoryDataDictionary]:
    """
    Pull one named GitHub release asset into memory as one or more dd
    sources.

    If asset_name is a "*.zip" archive (e.g. a "project-artifacts.zip"
    release bundle), it's opened in memory and every entry matching one of
    these conventions is returned as its own dd source:
    - "*_dd.*" / "*-dd.*"
    - "*_dictionary.*" / "*-dictionary.*"
    Matching is case-insensitive. Other files in the zip (schemas,
    enumerations, etc.) are ignored. Otherwise, this returns a single-item
    list, same as pull_release_dd().

    Nothing is ever written to disk.
    """

    from dbt_pipeline_utils.p_utils.github_release import pull_release_asset_to_memory

    content = pull_release_asset_to_memory(
        repository_url, asset_name, tag=tag, token=token, refresh=refresh
    )

    if not asset_name.lower().endswith(".zip"):
        return [
            InMemoryDataDictionary(
                filename=asset_name, content=content, source=repository_url, version=tag
            )
        ]

    sources = []
    with zipfile.ZipFile(BytesIO(content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue

            member_name = Path(info.filename).name
            if not _is_dd_filename(member_name):
                continue

            sources.append(
                InMemoryDataDictionary(
                    filename=member_name,
                    content=archive.read(info),
                    source=f"{repository_url}!{asset_name}",
                    version=tag,
                )
            )

    if not sources:
        raise FileNotFoundError(
            f"No DD files matching '*_dd.*'/'*-dd.*'/'*_dictionary.*'/'*-dictionary.*' "
            f"were found inside {asset_name} "
            f"from {repository_url}@{tag}."
        )

    return sources


def resolve_dd_sources(dd_sources: DDSource | Iterable[DDSource]) -> list[DDSource]:
    """
    Normalize a single path/source, a directory, or a list of paths/sources
    into a flat list. InMemoryDataDictionary entries pass through unchanged.

    Directories are scanned for data dictionary files only, i.e. filenames
    ending with "_dd"/"-dd" or "_dictionary"/"-dictionary" before the
    extension (csv/xlsx, case-insensitive). Other files in the directory are
    ignored. Explicitly-listed files are always included regardless of naming.
    """

    if isinstance(dd_sources, (str, Path, InMemoryDataDictionary)):
        dd_sources = [dd_sources]

    resolved: list[DDSource] = []
    for entry in dd_sources:
        if isinstance(entry, InMemoryDataDictionary):
            resolved.append(entry)
            continue

        path = Path(entry)
        if path.is_dir():
            dd_files = {
                p for p in path.iterdir() if p.is_file() and _is_dd_filename(p.name)
            }
            resolved.extend(sorted(dd_files))
        else:
            resolved.append(path)

    return resolved


def dd_source_descriptor(dd_source: DDSource) -> dict:
    """
    Return an identifying/versioning descriptor for a dd source: where it
    came from, its version/tag if any, and a content hash to detect real
    data changes regardless of naming.
    """
    if isinstance(dd_source, InMemoryDataDictionary):
        content_hash = hashlib.sha256(dd_source.content).hexdigest()[:12]
        return {
            "source": dd_source.source,
            "version": dd_source.version,
            "asset": dd_source.filename,
            "content_hash": content_hash,
        }

    path = Path(dd_source)
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return {
        "source": "local",
        "version": "",
        "asset": str(path),
        "content_hash": content_hash,
    }


LOG_FIELDNAMES = ["timestamp", "model", "source", "version", "asset", "content_hash"]


def log_dd_versions(log_filepath: Path, entries: Iterable[tuple[str, dict]]) -> None:
    """
    Append one row per (model_name, descriptor) to a CSV version log - but
    only if it differs from the last recorded row for that model, so
    re-running against unchanged data is a no-op and the log only grows when
    something actually changed.
    """
    log_filepath = Path(log_filepath)

    last_by_model: dict[str, dict] = {}
    if log_filepath.exists():
        with log_filepath.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                last_by_model[row["model"]] = row

    new_rows = []
    for model_name, descriptor in entries:
        last = last_by_model.get(model_name)
        if last and all(
            last.get(key, "") == str(descriptor.get(key, ""))
            for key in ("source", "version", "asset", "content_hash")
        ):
            continue

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model_name,
            **descriptor,
        }
        new_rows.append(row)
        last_by_model[model_name] = row

    if not new_rows:
        return

    log_filepath.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_filepath.exists()
    with log_filepath.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDNAMES)
        if write_header:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)
