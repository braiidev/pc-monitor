"""Tests de los lectores de /proc (readers), en especial el fix de ProcessLookupError."""

from __future__ import annotations

from pathlib import Path

import pytest

from monitor import readers


def _write_proc(
    tmp_path: Path, pid: str, stat: str | None = None, status: str | None = None
) -> Path:
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
    (
        proc / "999"
    ).mkdir()  # vive en listdir pero muere al leer su status (FileNotFoundError)
    (proc / "abc").mkdir()  # no es un pid -> se ignora
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    result = readers.read_procs()
    assert result == [(1024 * 1024, "123", "bash")]


def test_read_meminfo_parses_kb_to_bytes(monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "meminfo").write_text(
        "MemTotal:        16384 kB\nMemFree:          2048 kB\n"
    )
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    d = readers.read_meminfo()
    assert d["MemTotal"] == 16384 * 1024
    assert d["MemFree"] == 2048 * 1024


def _write_diskstats(tmp_path: Path, data: str) -> Path:
    proc = tmp_path / "proc"
    proc.mkdir(parents=True, exist_ok=True)
    (proc / "diskstats").write_text(data)
    return proc


def test_disk_stats_keeps_disks_and_drops_partitions(monkeypatch, tmp_path):
    # rows: major minor name rio rmerge rsect(5) ruse wio wmerge wsect(9) wuse ...
    row = "1 0 {name} 1000 0 8000 0 0 0 9000 0 0 0 0"
    proc = _write_diskstats(
        tmp_path,
        "\n".join(
            [
                row.format(name="sda"),
                row.format(name="sda1"),
                row.format(name="vda3"),
                row.format(name="nvme0n1"),
                row.format(name="nvme0n1p1"),
                row.format(name="mmcblk0"),
                row.format(name="mmcblk0p1"),
                row.format(name="loop0"),
                row.format(name="ram0"),
            ]
        ),
    )
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    stats = readers.disk_stats()
    assert set(stats) == {"sda", "nvme0n1", "mmcblk0"}
    assert stats["nvme0n1"] == (8000 * 512, 9000 * 512)


# ── Degradación elegante cuando Android bloquea /proc (EACCES sin root) ──
# En Android 13+ sin root, /proc/loadavg, /proc/stat, /proc/diskstats y
# /proc/net/dev devuelven PermissionError. Estos tests fijan que cada lector
# degrade a un valor vacío en vez de propagar la excepción (que rompía la TUI).


def _denied(*args, **kwargs):
    raise PermissionError(13, "Permission denied")


def test_read_loadavg_permission_error_returns_none(monkeypatch):
    monkeypatch.setattr("builtins.open", _denied)
    assert readers.read_loadavg() is None


def test_read_loadavg_ok_returns_string(monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "loadavg").write_text("0.42 0.30 0.25 1/234 5678\n")
    monkeypatch.setattr(readers, "PROC_PATH", proc)
    assert readers.read_loadavg() == "0.42 0.30 0.25 1/234 5678"


def test_read_cpu_lines_permission_error_returns_empty(monkeypatch):
    # /proc/stat bloqueado -> lista vacía -> cpu_pct_from_lines({}, {}) == {} -> vista "n/d".
    monkeypatch.setattr("builtins.open", _denied)
    assert readers.read_cpu_lines() == []


def test_cpu_pct_from_empty_lines_is_empty():
    assert readers.cpu_pct_from_lines([], []) == {}


def test_net_stats_permission_error_returns_empty(monkeypatch):
    monkeypatch.setattr("builtins.open", _denied)
    assert readers.net_stats() == {}


def test_disk_stats_permission_error_returns_empty(monkeypatch):
    monkeypatch.setattr("builtins.open", _denied)
    assert readers.disk_stats() == {}


def test_read_procs_permission_error_returns_empty(monkeypatch):
    # listdir de /proc también puede fallar: no debe lanzar.
    monkeypatch.setattr("os.listdir", lambda *a, **k: (_ for _ in ()).throw(PermissionError(13)))
    assert readers.read_procs() == []
