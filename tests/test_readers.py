"""Tests de los lectores de /proc (readers), en especial el fix de ProcessLookupError."""

from __future__ import annotations

from pathlib import Path

import pytest

from monitor import readers


def _write_proc(tmp_path: Path, pid: str, stat: str | None = None, status: str | None = None) -> Path:
    proc = tmp_path / "proc"
    (proc / pid).mkdir(parents=True, exist_ok=True)
    if stat is not None:
        (proc / pid / "stat").write_text(stat + "\n")
    if status is not None:
        (proc / pid / "status").write_text(status)
    return proc


def _stat_line(comm: str, utime: int = 11, stime: int = 12) -> str:
    # Tras el comm: state y fields 3..13, luego utime (field 14) y stime (field 15).
    tail = "S 1 2 3 4 5 6 7 8 9 10 {} {}".format(utime, stime)
    return f"123 ({comm}) {tail}"


def test_parse_proc_stat_with_spaces_in_comm():
    line = _stat_line("nginx: worker #2", utime=11, stime=12)
    parts = readers._parse_proc_stat(line)
    assert parts[0] == "S"
    assert parts[11] == "11"
    assert parts[12] == "12"


@pytest.mark.parametrize("comm", ["bash", "python test.py", "my proc with spaces"])
def test_cpu_time_with_comm(monkeypatch, tmp_path, comm):
    proc = _write_proc(tmp_path, "123", stat=_stat_line(comm, utime=30, stime=40))
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    assert readers.cpu_time("123") == 70


def test_cpu_time_missing_pid_returns_none(monkeypatch, tmp_path):
    proc = _write_proc(tmp_path, "123", stat=_stat_line("bash"))
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    assert readers.cpu_time("999") is None
    assert readers.cpu_time("123") == 23


def test_cpu_time_malformed_returns_none(monkeypatch, tmp_path):
    proc = _write_proc(tmp_path, "123", stat="malformed")
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    assert readers.cpu_time("123") is None


def test_cpu_time_process_lookup_error_returns_none(monkeypatch, tmp_path):
    # Proceso que muere justo antes de leer su stat -> ProcessLookupError (subclase de OSError).
    proc = _write_proc(tmp_path, "123", stat=_stat_line("bash"))

    def boom(*args, **kwargs):
        raise ProcessLookupError("no such process")

    monkeypatch.setattr(readers, "PROC_PATH", proc)
    monkeypatch.setattr("builtins.open", boom)
    assert readers.cpu_time("123") is None


def test_read_procs_skips_dead_processes(monkeypatch, tmp_path):
    status_ok = "Name:\tbash\nVmRSS:\t1024 kB\n"
    proc = _write_proc(tmp_path, "123", status=status_ok)
    (proc / "999").mkdir()  # vive en listdir pero muere al leer su status (FileNotFoundError)
    (proc / "abc").mkdir()  # no es un pid -> se ignora
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    result = readers.read_procs()
    assert result == [(1024 * 1024, "123", "bash")]


def test_read_meminfo_parses_kb_to_bytes(monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "meminfo").write_text("MemTotal:        16384 kB\nMemFree:          2048 kB\n")
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    d = readers.read_meminfo()
    assert d["MemTotal"] == 16384 * 1024
    assert d["MemFree"] == 2048 * 1024