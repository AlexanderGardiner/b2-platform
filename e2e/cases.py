from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CERTIFICATE_NAMES = ("certificate.png", "certificate.jpg", "certificate.jpeg", "certificate.pdf")
MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}


@dataclass(frozen=True)
class Case:
    country: str
    kind: str
    case_id: str
    path: Path
    narrative: str | None
    certificate_path: Path | None
    expected: dict[str, Any]

    @property
    def wa_id(self) -> str:
        return f"e2e-{self.country}-{self.kind}-{self.case_id}"

    @property
    def label(self) -> str:
        return f"{self.country}/{self.kind}/{self.case_id}"


def discover_cases(root: Path, *, country: str | None, kind: str | None) -> list[Case]:
    if not root.exists():
        return []

    cases: list[Case] = []
    country_dirs = [root / country] if country else sorted(path for path in root.iterdir() if path.is_dir())
    for country_dir in country_dirs:
        if not country_dir.is_dir():
            continue
        kind_dirs = [country_dir / kind] if kind else [country_dir / "real", country_dir / "fake"]
        for kind_dir in kind_dirs:
            if not kind_dir.is_dir():
                continue
            for case_dir in sorted(path for path in kind_dir.iterdir() if path.is_dir()):
                cases.append(load_case(root, case_dir))
    return cases


def load_case(root: Path, case_dir: Path) -> Case:
    rel = case_dir.relative_to(root)
    country, kind, case_id = rel.parts[:3]
    narrative_path = case_dir / "narrative.txt"
    expected_path = case_dir / "expected.json"

    narrative = narrative_path.read_text(encoding="utf-8").strip() if narrative_path.exists() else None
    expected = load_expected(expected_path)
    certificate_path = find_certificate(case_dir)

    return Case(
        country=country,
        kind=kind,
        case_id=case_id,
        path=case_dir,
        narrative=narrative or None,
        certificate_path=certificate_path,
        expected=expected,
    )


def load_expected(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"expected_outcome": "accept"}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def find_certificate(case_dir: Path) -> Path | None:
    named = [case_dir / name for name in CERTIFICATE_NAMES]
    matches = [path for path in named if path.exists()]
    if not matches:
        matches = [
            path
            for path in sorted(case_dir.iterdir())
            if path.is_file() and path.stem == "certificate" and path.suffix.lower() in MEDIA_EXTENSIONS
        ]
    if len(matches) > 1:
        raise ValueError(f"{case_dir} has multiple certificate files")
    return matches[0] if matches else None

