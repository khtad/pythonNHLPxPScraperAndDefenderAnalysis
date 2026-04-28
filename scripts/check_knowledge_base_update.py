"""Check whether a change set has an auditable knowledge-base update.

The project requires knowledge-base maintenance before opening or updating a
pull request. This script makes that rule easy to run from an agent checklist:
if code, notebooks, roadmap docs, or validation artifacts changed, either
`knowledge_base/log.md` must be part of the change set or the caller must pass
an explicit no-update reason for PR notes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE_RELEVANT_PREFIXES = (
    "src/",
    "notebooks/",
    "docs/",
    "artifacts/",
)
KNOWLEDGE_RELEVANT_FILES = {
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
    "requirements.txt",
}
IGNORED_PREFIXES = (
    ".claude/",
    ".pytest-tmp/",
    "pytest_tmp",
    "data/",
)
KB_LOG_PATH = "knowledge_base/log.md"


def normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def changed_files_requiring_kb_review(changed_files: list[str]) -> list[str]:
    """Return changed files whose content should trigger KB review."""
    relevant = []
    for raw_path in changed_files:
        path = normalize_path(raw_path)
        if not path or path.startswith("knowledge_base/"):
            continue
        if any(path.startswith(prefix) for prefix in IGNORED_PREFIXES):
            continue
        if (
            path in KNOWLEDGE_RELEVANT_FILES
            or any(path.startswith(prefix) for prefix in KNOWLEDGE_RELEVANT_PREFIXES)
        ):
            relevant.append(path)
    return sorted(set(relevant))


def has_kb_audit(changed_files: list[str]) -> bool:
    """Return True if the change set includes the KB audit log."""
    return KB_LOG_PATH in {normalize_path(path) for path in changed_files}


def _git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def collect_changed_files(base_ref: str) -> list[str]:
    """Collect committed, staged, unstaged, and untracked changed paths."""
    changed: set[str] = set()

    try:
        changed.update(_git_lines(["diff", "--name-only", f"{base_ref}...HEAD"]))
    except subprocess.CalledProcessError:
        changed.update(_git_lines(["diff", "--name-only", "HEAD"]))

    changed.update(_git_lines(["diff", "--name-only", "--cached"]))
    changed.update(_git_lines(["diff", "--name-only"]))
    changed.update(_git_lines(["ls-files", "--others", "--exclude-standard"]))
    return sorted(normalize_path(path) for path in changed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify that knowledge-relevant changes have KB audit coverage."
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base ref used for committed changes; worktree changes are always included.",
    )
    parser.add_argument(
        "--no-kb-needed",
        default=None,
        help=(
            "Explicit reason why no wiki/log update is needed. Include the same "
            "reason in PR notes."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    changed_files = collect_changed_files(args.base_ref)
    review_files = changed_files_requiring_kb_review(changed_files)

    if not review_files:
        print("No knowledge-relevant files changed.")
        return 0

    if has_kb_audit(changed_files):
        print("Knowledge-base audit detected in knowledge_base/log.md.")
        return 0

    if args.no_kb_needed:
        print("No knowledge-base update recorded; explicit reason supplied:")
        print(args.no_kb_needed)
        return 0

    print("Knowledge-relevant files changed without a KB audit entry:")
    for path in review_files:
        print(f"  - {path}")
    print(
        "\nUpdate affected knowledge_base/wiki pages and knowledge_base/log.md, "
        "or rerun with --no-kb-needed and include that reason in PR notes."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
