"""
In-memory cache for pulled release artifacts.

Avoids re-hitting a repository's release endpoint every time you generate
something from the same version. Pass refresh=True to a release-pulling
function to force a fresh pull (e.g. after a new release was tagged under
the same tag name), or call clear_release_cache() to drop everything cached
so far. Pulling a different `tag` is never served from an older tag's cache
entry, since the tag is part of every cache key.

The cache lives only for the current process - nothing is persisted to disk.
"""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_CACHE: dict[tuple, object] = {}


def cached_pull(key: tuple, refresh: bool, pull_fn: Callable[[], T]) -> T:
    """Return the cached value for key, or call pull_fn() and cache its result."""
    if not refresh and key in _CACHE:
        return _CACHE[key]  # type: ignore[return-value]

    value = pull_fn()
    _CACHE[key] = value
    return value


def clear_release_cache(key: tuple | None = None) -> None:
    """Clear the whole in-memory release cache, or just one entry if key is given."""
    if key is None:
        _CACHE.clear()
    else:
        _CACHE.pop(key, None)
