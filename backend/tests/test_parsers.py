from datetime import datetime

from parsers.auto_parser import detect_and_parse
from parsers.base_parser import LogLevel, LogSource
from parsers.docker_parser import DockerParser
from parsers.nginx_parser import NginxParser
from parsers.python_parser import PythonParser


def test_nginx_parses_access_log():
    p = NginxParser()
    lines = [
        '127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "-" "Mozilla"',
        '127.0.0.1 - - [10/Oct/2000:13:55:37 -0700] "POST /x HTTP/1.0" 500 0 "-" "-"',
    ]
    out = p.parse(lines)
    assert len(out) == 2
    assert out[0].status_code == 200
    assert out[0].level == LogLevel.INFO
    assert out[1].status_code == 500
    assert out[1].level == LogLevel.ERROR


def test_nginx_parses_error_log():
    p = NginxParser()
    lines = [
        "2024/01/15 12:34:56 [error] 1234#1234: *1 connect() failed (111: Connection refused)",
    ]
    out = p.parse(lines)
    assert len(out) == 1
    assert out[0].level == LogLevel.ERROR
    assert "connect()" in out[0].message


def test_python_parses_traceback():
    p = PythonParser()
    lines = [
        "Traceback (most recent call last):",
        '  File "app.py", line 1, in <module>',
        "    raise ValueError('x')",
        "ValueError: x",
    ]
    out = p.parse(lines)
    assert len(out) == 1
    assert out[0].stack_trace is not None
    assert "ValueError" in out[0].stack_trace


def test_python_parses_uvicorn():
    p = PythonParser()
    lines = ['INFO:     127.0.0.1:12345 - "GET / HTTP/1.1" 200 OK']
    out = p.parse(lines)
    assert len(out) == 1
    assert out[0].status_code == 200


def test_docker_parses_stdout():
    p = DockerParser()
    lines = [
        "2024-01-15T12:34:56.789012345Z stdout F hello world",
        "myapp | 2024-01-15 12:34:56 ERROR boom",
    ]
    out = p.parse(lines)
    assert len(out) == 2
    assert out[0].metadata.get("stream") == "stdout"
    assert out[1].service == "myapp"


def test_auto_detects_nginx():
    text = '127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET / HTTP/1.0" 200 1 "-" "-"'
    entries, src, _sk = detect_and_parse(text)
    assert src == LogSource.NGINX
    assert len(entries) == 1


def test_auto_detects_python():
    text = "2024-01-15 12:00:00,000 ERROR mod:1 something failed\n"
    entries, src, _ = detect_and_parse(text)
    assert src == LogSource.PYTHON
    assert entries[0].level == LogLevel.ERROR


def test_auto_falls_back_generic():
    text = "2024-01-15 12:00:00 noise without real format markers xyz\n"
    entries, src, _ = detect_and_parse(text)
    assert src == LogSource.UNKNOWN
    assert len(entries) >= 1
