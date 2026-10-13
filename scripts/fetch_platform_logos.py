"""Fetch the pinned Monochrome Gaming Logos SVG release for local development.

The generated assets deliberately stay outside version control. Platform-logo
mappings only store a path below ``static/icons/platforms`` and stay portable
between installations that have run ``make setup``.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile


REPOSITORY = "HVR88/Monochrome-Gaming-Logos"
DEFAULT_REF = "7eb7ddb7246fa5c39b71d5136e7a527bac03fb7f"
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "static" / "icons" / "platforms"


def fetch(ref: str) -> int:
    url = f"https://codeload.github.com/{REPOSITORY}/zip/{ref}"
    request = Request(url, headers={"User-Agent": "Shelf platform-logo setup"})
    with urlopen(request, timeout=60) as response:
        archive = ZipFile(io.BytesIO(response.read()))

    # GitHub wraps archives in ``Monochrome-Gaming-Logos-<ref>/``. Only accept
    # direct entries under its svg directory; no archive member can escape the
    # dedicated destination directory.
    members = [
        member for member in archive.infolist()
        if member.filename.count("/") == 2
        and member.filename.split("/")[1] == "svg"
        and member.filename.endswith(".svg")
    ]
    if not members:
        raise RuntimeError("The logo archive did not contain any SVG assets")

    DESTINATION.mkdir(parents=True, exist_ok=True)
    for member in members:
        target = DESTINATION / Path(member.filename).name
        target.write_bytes(archive.read(member))
    return len(members)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch bundled platform SVG logos")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Git commit or tag to download")
    args = parser.parse_args()
    count = fetch(args.ref)
    print(f"Installed {count} platform logos in {DESTINATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
