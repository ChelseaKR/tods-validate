"""Reporting additions: by-rule grouping, root-cause hints, SARIF, HTML."""

from tods_validate.findings import Finding, Severity
from tods_validate.report import (
    REPORT_SCHEMA_VERSION,
    by_rule,
    render_html,
    render_markdown,
    render_sarif,
    render_text,
)


def _findings(rule_id: str, n: int, severity: Severity = Severity.ERROR) -> list[Finding]:
    return [
        Finding(rule_id=rule_id, severity=severity, file="run_events.txt", row=i, message=f"m{i}")
        for i in range(2, 2 + n)
    ]


def test_by_rule_counts() -> None:
    findings = _findings("TODS-E307", 3) + _findings("TODS-E308", 1)
    counts = by_rule(findings)
    assert counts["TODS-E307"] == 3
    assert counts["TODS-E308"] == 1


def test_text_shows_breakdown_and_path_to_green() -> None:
    text = render_text(_findings("TODS-E307", 2), "feed/")
    assert "By rule: TODS-E307 ×2" in text
    assert "away from a clean run" in text


def test_text_shows_root_cause_hint_when_clustered() -> None:
    text = render_text(_findings("TODS-E307", 6), "feed/")
    assert "hint:" in text
    assert "stale" in text


def test_text_hint_includes_worked_example_when_clustered() -> None:
    text = render_text(_findings("TODS-E307", 6), "feed/")
    assert "Before:" in text
    assert "After:" in text


def test_markdown_hint_includes_worked_example_when_clustered() -> None:
    markdown = render_markdown(_findings("TODS-E307", 6), "feed/")
    assert "hint:" in markdown
    assert "Before:" in markdown
    assert "After:" in markdown


def test_max_findings_hides_overflow() -> None:
    text = render_text(_findings("TODS-E307", 10), "feed/", max_findings=3)
    assert "7 more finding(s) not shown" in text


def test_sarif_lists_rules_and_results() -> None:
    import json

    sarif = json.loads(render_sarif(_findings("TODS-E307", 2), "feed/"))
    driver = sarif["runs"][0]["tool"]["driver"]
    assert {r["id"] for r in driver["rules"]} == {"TODS-E307"}
    assert len(sarif["runs"][0]["results"]) == 2
    loc = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "run_events.txt"


def test_sarif_help_uri_is_a_stable_rule_page() -> None:
    """helpUri points at the permanent per-rule page (EXP-08), not the spec

    citation directly, so links keep resolving even if the spec text moves.
    The spec citation itself is not lost -- it survives as a property.
    """
    import json

    from tods_validate.report import RULE_PAGE_BASE
    from tods_validate.rules import all_rules

    sarif = json.loads(render_sarif(_findings("TODS-E307", 1), "feed/"))
    descriptor = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    rule = next(r for r in all_rules() if r.id == "TODS-E307")
    assert descriptor["helpUri"] == f"{RULE_PAGE_BASE}{rule.id}.html"
    assert descriptor["helpUri"].endswith(f"{rule.id}.html")
    assert descriptor["properties"]["specSection"] == rule.spec_section


def test_html_escapes_and_is_standalone() -> None:
    nasty = [Finding(rule_id="TODS-E999", severity=Severity.ERROR, message="<script>x</script>")]
    out = render_html(nasty, "feed/")
    assert "<script>x</script>" not in out  # escaped
    assert "&lt;script&gt;" in out


def test_html_report_is_accessible() -> None:
    out = render_html(_findings("TODS-E307", 2), "feed/")
    # Declared language and a responsive viewport so the page reflows on zoom.
    assert "<html lang='en'>" in out
    assert "name='viewport'" in out
    # Document landmarks give assistive tech an outline.
    assert "<header>" in out
    assert "<main>" in out
    # The findings table is navigable: a caption plus column-scoped headers.
    assert "<caption>" in out
    assert out.count("scope='col'") == 4
    # Severity reaches a screen reader as a word, not color alone.
    assert ">ERROR<" in out


def test_html_severity_colors_clear_contrast() -> None:
    # The info green was lightened away from the original low-contrast #0b5 so
    # all three severities clear WCAG AA (4.5:1) on the white background.
    out = render_html([], "feed/")
    assert "#0b5" not in out
    assert ".sev-info{color:#0a7d3f}" in out


def _luminance(hexcolor: str) -> float:
    hexcolor = hexcolor.lstrip("#")
    r, g, b = (int(hexcolor[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def test_html_severity_colors_clear_contrast_light_and_dark() -> None:
    # Both palettes must clear WCAG AA (4.5:1) against their own background.
    light_bg = "#ffffff"
    dark_bg = "#121212"
    light = {"error": "#b00020", "warning": "#8a5a00", "info": "#0a7d3f"}
    dark = {"error": "#ff6b6b", "warning": "#e0a530", "info": "#3ddc84"}
    for color in light.values():
        assert _contrast(color, light_bg) >= 4.5
    for color in dark.values():
        assert _contrast(color, dark_bg) >= 4.5


def test_html_declares_dark_scheme() -> None:
    out = render_html(_findings("TODS-E307", 2), "feed/")
    assert "color-scheme:light dark" in out
    assert "@media (prefers-color-scheme: dark)" in out


def test_html_groups_findings_by_rule_with_details_summary() -> None:
    findings = _findings("TODS-E307", 3) + _findings("TODS-E308", 1)
    out = render_html(findings, "feed/")
    assert "<details class='rule-group' open>" in out
    assert "<summary>TODS-E307 - 3 findings</summary>" in out
    assert "<summary>TODS-E308 - 1 finding</summary>" in out
    # Two rules, two groups, two per-group tables — headers repeat per group.
    assert out.count("<caption>") == 2
    assert out.count("scope='col'") == 8


def test_html_shows_showing_n_of_m_counter_without_js() -> None:
    out = render_html(_findings("TODS-E307", 5), "feed/")
    assert "Showing 5 of 5 findings" in out


def test_html_has_inline_filter_controls_and_no_external_assets() -> None:
    out = render_html(_findings("TODS-E307", 3) + _findings("TODS-E308", 2), "feed/")
    assert "id='sev-filter'" in out
    assert "id='rule-filter'" in out
    assert "id='file-filter'" in out
    assert "<script>" in out
    # Single-file, no-network contract: no external asset references.
    assert "http://" not in out
    assert "https://" not in out


def test_html_ten_thousand_findings_renders_as_single_deterministic_string() -> None:
    rule_ids = [f"TODS-E{300 + (i % 20)}" for i in range(10_000)]
    findings = [
        Finding(
            rule_id=rule_ids[i],
            severity=Severity(i % 3),
            message=f"finding {i}",
            file=f"file{i % 50}.txt",
            row=i,
        )
        for i in range(10_000)
    ]
    out1 = render_html(findings, "feed/")
    out2 = render_html(findings, "feed/")
    assert isinstance(out1, str)
    assert "http://" not in out1
    assert "https://" not in out1
    assert "Showing 10000 of 10000 findings" in out1
    # Rendering twice from the same input is byte-identical (golden-file safe).
    assert out1 == out2


def test_markdown_stamp_is_optional() -> None:
    plain = render_markdown(_findings("TODS-E307", 1), "feed/")
    stamped = render_markdown(_findings("TODS-E307", 1), "feed/", stamp=True)
    assert "Generated by tods-validate" not in plain
    assert "Generated by tods-validate" in stamped


def test_report_schema_version_is_set() -> None:
    assert REPORT_SCHEMA_VERSION
