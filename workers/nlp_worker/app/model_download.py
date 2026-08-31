from __future__ import annotations

import argparse
from pathlib import Path

from .model import download_pinned_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and checksum-verify the pinned T4A multilingual encoder"
    )
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    download_pinned_model(Path(args.target))


if __name__ == "__main__":
    main()
