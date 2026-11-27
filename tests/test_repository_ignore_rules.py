"""Ignore rules must never silently drop vendored benchmark source.

Benchmark packs vendor upstream repositories verbatim. An unanchored ignore rule
matches at every depth, so a generic name such as ``result`` also matches an
upstream package directory: the files stay on the authoring machine, never enter
Git, and every later clone holds a pack that no longer compiles. These paths are
the ones that regression actually hit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Real upstream package directories of the vendored Paper plugins.
VENDORED_SOURCE_PATHS = (
    "benchmarks/minecraft-core/private/harbor/multiverse-core-world-exists-by-key"
    "/environment/plugin/src/main/java/org/mvplugins/multiverse/core/utils/result/Attempt.java",
    "benchmarks/minecraft-core/private/harbor/multiverse-core-world-exists-by-key"
    "/tests/starter/src/main/java/org/mvplugins/multiverse/core/utils/result/FailureReason.java",
    "benchmarks/minecraft-core/private/harbor/chatty-bad-channel-disables-plugin"
    "/environment/plugin/api/src/main/java/ru/brikster/chatty/api/chat/message/strategy/result"
    "/MessageTransformResult.java",
    "benchmarks/minecraft-core/private/harbor/chatty-bad-channel-disables-plugin"
    "/tests/starter/spigot/src/main/java/ru/brikster/chatty/chat/message/transform/result"
    "/MessageTransformResultImpl.java",
    # The same rule class would swallow plugin, provider and core source too.
    "plugins/minecraft/src/rhenium_minecraft/result/marker.py",
    "src/rhenium/result/marker.py",
    "tools/authoring/src/rhenium_authoring/result/marker.py",
)


def _ignored(paths: tuple[str, ...]) -> set[str]:
    """The subset of ``paths`` that the repository's ignore rules match."""
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=ROOT,
        input="\n".join(paths),
        capture_output=True,
        text=True,
        check=False,
    )
    # 0: at least one path matched, 1: none matched. Anything else is a real error.
    assert result.returncode in (0, 1), result.stderr
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_vendored_benchmark_source_is_never_ignored() -> None:
    assert _ignored(VENDORED_SOURCE_PATHS) == set()


def test_the_nix_build_symlink_stays_ignored_at_the_repository_root() -> None:
    assert _ignored(("result",)) == {"result"}
