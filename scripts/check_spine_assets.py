#!/usr/bin/env python3
"""CLI wrapper around app.services.spine_assets's atlas checks — see that
module's docstring for what's validated and why.

Usage:
    python scripts/check_spine_assets.py front/img/east-discovery
    python scripts/check_spine_assets.py front/img/east-discovery --fix
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.spine_assets import check_dir, find_atlas_dirs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", help="directory to scan recursively (e.g. front/img/east-discovery)")
    parser.add_argument("--fix", action="store_true", help="apply fixes instead of only reporting")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: '{root}' is not a directory", file=sys.stderr)
        sys.exit(1)

    all_issues: list[str] = []
    for d in find_atlas_dirs(root):
        all_issues.extend(check_dir(d, args.fix))

    if not all_issues:
        print(f"OK — no Spine asset issues found under {root}")
        return

    verb = "Fixed" if args.fix else "Found"
    print(f"{verb} {len(all_issues)} issue(s):")
    for issue in all_issues:
        print(f"  - {issue}")

    if not args.fix:
        sys.exit(1)


if __name__ == "__main__":
    main()
