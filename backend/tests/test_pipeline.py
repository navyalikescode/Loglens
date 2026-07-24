import pytest

from parsers.base_parser import LogLevel, LogSource
from pipeline.processor import LogProcessor
from report.formatter import ReportFormatter
from report.generator import ReportGenerator


def test_full_pipeline_nginx():
    text = (
        '127.0.0.1 - - [15/Jan/2024:12:00:00 +0000] "GET / HTTP/1.1" 500 0 "-" "-"'
    )
    r = LogProcessor().process(text)
    assert r.log_source == LogSource.NGINX
    assert r.total_lines == 1
    assert r.parsed_lines >= 1


def test_full_pipeline_python():
    text = (
        "Traceback (most recent call last):\n"
        '  File "x.py", line 1, in <module>\n'
        "    1/0\n"
        "ZeroDivisionError: division by zero\n"
    )
    r = LogProcessor().process(text)
    assert r.log_source == LogSource.PYTHON
    assert any(c.category == "code_error" for c in r.root_causes)


def test_pipeline_handles_empty_log():
    r = LogProcessor().process("")
    assert r.total_lines == 0
    assert r.parsed_lines == 0


def test_pipeline_handles_malformed():
    r = LogProcessor().process("@@@ not a log @@@\n###\n")
    assert r.parsed_lines >= 1


def test_report_generator_template_fallback():
    text = "2024-01-15 12:00:00,000 ERROR x:1 boom\n"
    res = LogProcessor().process(text)
    out = ReportGenerator().generate(res)
    assert "## Incident Summary" in out
    assert "## Root Cause Analysis" in out


def test_report_json_has_required_fields():
    text = "2024-01-15 12:00:00,000 ERROR x:1 boom\n"
    res = LogProcessor().process(text)
    md = ReportGenerator().generate(res)
    js = ReportFormatter().to_json(md, res)
    for k in (
        "metadata",
        "severity",
        "summary",
        "root_causes",
        "anomalies",
        "error_clusters",
        "timeline",
        "incident_report_markdown",
    ):
        assert k in js


def test_severity_p1_on_critical():
    from analysis.root_cause_analyzer import RootCause
    from pipeline.processor import AnalysisResult

    res = AnalysisResult(
        log_source=LogSource.PYTHON,
        total_lines=1,
        parsed_lines=1,
        skipped_lines=0,
        time_range=(None, None),
        critical_count=1,
        root_causes=[
            RootCause(
                hypothesis="h",
                confidence="high",
                evidence=["e"],
                category="memory",
                first_signal_at=None,
                recommended_actions=["a"],
            )
        ],
    )
    assert ReportFormatter().infer_severity(res) == "P1"


def test_severity_p4_on_clean():
    from pipeline.processor import AnalysisResult

    res = AnalysisResult(
        log_source=LogSource.NGINX,
        total_lines=5,
        parsed_lines=5,
        skipped_lines=0,
        time_range=(None, None),
        error_rate=0.0,
        warning_rate=0.0,
        critical_count=0,
    )
    assert ReportFormatter().infer_severity(res) == "P4"
