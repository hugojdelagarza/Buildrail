from pathlib import Path

import pytest

from buildrail.testing import detect_coverage


def test_missing_coverage_file_returns_none(tmp_path: Path) -> None:
    assert detect_coverage(tmp_path) is None


def test_valid_cobertura_coverage_is_parsed(tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text(
        '<?xml version="1.0"?>\n'
        '<coverage line-rate="0.87" lines-covered="87" lines-valid="100"></coverage>\n',
        encoding="utf-8",
    )

    coverage = detect_coverage(tmp_path)

    assert coverage is not None
    assert coverage.source == "coverage.xml"
    assert coverage.line_rate == 0.87
    assert coverage.lines_covered == 87
    assert coverage.lines_valid == 100


def test_malformed_xml_returns_none(tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text("not valid xml <<<", encoding="utf-8")

    assert detect_coverage(tmp_path) is None


def test_wrong_root_tag_returns_none(tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text("<not-coverage></not-coverage>", encoding="utf-8")

    assert detect_coverage(tmp_path) is None


def test_missing_line_rate_returns_none(tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text("<coverage></coverage>", encoding="utf-8")

    assert detect_coverage(tmp_path) is None


def test_never_invokes_coverage_tooling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("detect_coverage must never launch a subprocess")

    monkeypatch.setattr("subprocess.run", _explode)

    assert detect_coverage(tmp_path) is None
