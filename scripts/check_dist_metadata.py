"""Fail when the built distributions carry metadata PyPI would render wrongly.

Every field compared here is read out of the *artifact* -- the wheel's
``dist-info/METADATA`` and the sdist's ``PKG-INFO`` -- and not out of
``pyproject.toml``. A check that reads ``[project.urls]`` and then asserts
something about ``[project.urls]`` reports a pass it did not earn, in the same
way ``contractVersion`` used to in :mod:`scripts.check_public_contract`: the
declaration cannot disagree with itself.

It is not a hypothetical failure. The sibling ``gauntlet-evals`` 0.2.0 wheel was
published with no ``Project-URL`` lines at all while ``pyproject.toml`` on the
default branch declared four of them, because the release built from a tag cut
before that change merged. Every source-level assertion in that repository
passed, the defect was only visible on the index page, and published metadata is
immutable -- it took a 0.3.0 to clear it.

``pyproject.toml`` is read for exactly two values, the expected version and the
expected ``requires-python``, and both are then asserted *against* the artifact,
so a stale build fails here rather than passing quietly.

Standard library only: this also runs in the publish job, which builds with
``python -m build`` and has no development environment.

Usage::

    python scripts/check_dist_metadata.py dist
    python scripts/check_dist_metadata.py dist-published --wheel-only
"""

from __future__ import annotations

import argparse
import email.parser
import email.policy
import re
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass
from email.message import Message
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DISTRIBUTION = "tods-validate"
LICENSE_EXPRESSION = "Apache-2.0"

# Homepage and Issues are what #223 was about: without them the PyPI page offers
# a reader the source tree and the upstream spec and no route to the playground
# or to a way of reporting anything. Changelog is here because a validator's
# users need to know what changed between two releases of the rules.
REQUIRED_URL_LABELS = ("Homepage", "Repository", "Issues", "Changelog")


@dataclass(frozen=True)
class Result:
    """One named field check and what the artifact actually said."""

    name: str
    ok: bool
    detail: str


def _normalize(name: str) -> str:
    """Apply PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse(raw: bytes) -> Message:
    return email.parser.BytesParser(policy=email.policy.compat32).parsebytes(raw)


def _description(msg: Message) -> str:
    """The long description: the payload in current metadata, else the header."""
    payload = msg.get_payload(decode=False)
    if isinstance(payload, str) and payload.strip():
        return payload
    return str(msg.get("Description") or "")


def _read_wheel(path: Path) -> Message:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise SystemExit(f"{path.name}: expected one dist-info/METADATA, found {names}")
        return _parse(archive.read(names[0]))


def _read_sdist(path: Path) -> Message:
    with tarfile.open(path) as archive:
        names = [n for n in archive.getnames() if n.count("/") == 1 and n.endswith("/PKG-INFO")]
        if len(names) != 1:
            raise SystemExit(f"{path.name}: expected one top-level PKG-INFO, found {names}")
        handle = archive.extractfile(names[0])
        if handle is None:
            raise SystemExit(f"{path.name}: PKG-INFO is not a regular file")
        with handle:
            return _parse(handle.read())


def _expected_from_source() -> tuple[str, str]:
    """``(version, requires-python)`` as declared in pyproject.toml."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return str(project["version"]), str(project["requires-python"])


def _check_identity(msg: Message, version: str) -> list[Result]:
    name = str(msg.get("Name") or "")
    got = str(msg.get("Version") or "")
    return [
        Result(
            "name is the published distribution name",
            _normalize(name) == DISTRIBUTION,
            f"Name: {name!r} (expected {DISTRIBUTION!r})",
        ),
        Result(
            "version matches the source tree",
            got == version,
            f"Version: {got!r} (pyproject says {version!r})",
        ),
    ]


def _check_requires_python(msg: Message, requires_python: str) -> list[Result]:
    got = str(msg.get("Requires-Python") or "")
    return [
        Result(
            "requires-python is present and matches the source tree",
            got == requires_python,
            f"Requires-Python: {got!r} (pyproject says {requires_python!r})",
        )
    ]


def _check_license(msg: Message) -> list[Result]:
    expression = str(msg.get("License-Expression") or "")
    legacy = msg.get("License")
    text = str(legacy) if legacy is not None else ""
    return [
        Result(
            "license is a PEP 639 SPDX expression",
            expression == LICENSE_EXPRESSION,
            f"License-Expression: {expression!r} (expected {LICENSE_EXPRESSION!r})",
        ),
        Result(
            # `license = { file = "LICENSE" }` resolves to the file's contents,
            # so the index page's License field becomes the whole license text.
            # outcome-receipts published exactly that; it is cheap to refuse here.
            "no legacy License field carrying license text",
            legacy is None,
            "License: absent"
            if legacy is None
            else f"License: present, {len(text.splitlines())} lines, "
            f"{len(text)} characters -- PyPI renders all of it",
        ),
    ]


def _check_urls(msg: Message) -> list[Result]:
    entries: dict[str, str] = {}
    for raw in msg.get_all("Project-URL") or []:
        label, _, url = str(raw).partition(",")
        entries[label.strip()] = url.strip()
    missing = [label for label in REQUIRED_URL_LABELS if label not in entries]
    relative = sorted(label for label, url in entries.items() if not url.startswith("https://"))
    return [
        Result(
            "every required Project-URL label is published",
            not missing,
            f"labels {sorted(entries)}; missing {missing or 'none'}",
        ),
        Result(
            "every published Project-URL is an absolute https URL",
            not relative,
            f"not absolute https: {relative or 'none'}",
        ),
    ]


def _check_description(msg: Message) -> list[Result]:
    description = _description(msg)
    content_type = str(msg.get("Description-Content-Type") or "")
    return [
        Result(
            "the rendered description declares its content type",
            content_type.startswith("text/"),
            f"Description-Content-Type: {content_type!r}",
        ),
        Result(
            "the rendered description is not empty",
            bool(description.strip()),
            f"description is {len(description)} characters",
        ),
    ]


def check(msg: Message, version: str, requires_python: str) -> list[Result]:
    """Every field check, against one parsed metadata document."""
    return [
        *_check_identity(msg, version),
        *_check_requires_python(msg, requires_python),
        *_check_license(msg),
        *_check_urls(msg),
        *_check_description(msg),
    ]


def _agreement(wheel: Message, sdist: Message) -> Result:
    """The wheel and the sdist must tell PyPI the same story."""
    fields = ("Name", "Version", "Requires-Python", "License-Expression", "License")
    disagreements = [
        field
        for field in fields
        if [str(v) for v in (wheel.get_all(field) or [])]
        != [str(v) for v in (sdist.get_all(field) or [])]
    ]
    if sorted(str(v) for v in (wheel.get_all("Project-URL") or [])) != sorted(
        str(v) for v in (sdist.get_all("Project-URL") or [])
    ):
        disagreements.append("Project-URL")
    return Result(
        "the wheel and the sdist agree on what PyPI is told",
        not disagreements,
        f"fields that disagree: {disagreements or 'none'}",
    )


def _one(paths: list[Path], kind: str) -> Path:
    if len(paths) != 1:
        raise SystemExit(f"expected exactly one {kind}, found {[p.name for p in paths]}")
    return paths[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check built distribution metadata.")
    parser.add_argument("dist_dir", type=Path, help="directory holding the built wheel and sdist")
    parser.add_argument(
        "--wheel-only",
        action="store_true",
        help="check a lone wheel, e.g. one already published and downloaded back",
    )
    args = parser.parse_args(argv)

    version, requires_python = _expected_from_source()
    wheel_path = _one(sorted(args.dist_dir.glob("*.whl")), "wheel")
    wheel = _read_wheel(wheel_path)
    results = check(wheel, version, requires_python)
    measured = [f"wheel {wheel_path.name}"]

    if not args.wheel_only:
        sdist_path = _one(sorted(args.dist_dir.glob("*.tar.gz")), "sdist")
        results.append(_agreement(wheel, _read_sdist(sdist_path)))
        measured.append(f"sdist {sdist_path.name}")

    print(f"checking published metadata in {', '.join(measured)}")
    for result in results:
        print(f"  [{'PASS' if result.ok else 'FAIL'}] {result.name}\n         {result.detail}")
    passed = sum(1 for result in results if result.ok)
    print(f"\nfields correct in the artifact / fields examinable: {passed}/{len(results)}")
    if passed != len(results):
        print(
            "\nPublished metadata is immutable: a released version cannot be edited in "
            "place, so a wrong field here is only ever cleared by a new release."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
