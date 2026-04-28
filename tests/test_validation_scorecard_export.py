import importlib.util
import subprocess
from pathlib import Path

import pytest


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_validation_scorecard.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "export_validation_scorecard", _SCRIPT_PATH
)
exporter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(exporter)


class _FakeProcess:
    def __init__(self, *, wait_timeout=False):
        self.wait_timeout = wait_timeout
        self.terminated = False
        self.killed = False
        self.wait_timeouts = []

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        if self.wait_timeout and timeout is not None:
            raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
        return -15 if self.terminated or self.killed else 0


def test_run_command_with_progress_terminates_child_on_interrupt(monkeypatch):
    process = _FakeProcess()
    monkeypatch.setattr(exporter.subprocess, "Popen", lambda *_, **__: process)
    monkeypatch.setattr(exporter, "_progress", lambda *_, **__: None)
    monkeypatch.setattr(
        exporter.time,
        "sleep",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        exporter._run_command_with_progress(
            ["fake"],
            label="notebook execution",
            progress_interval_seconds=30,
            run_started_at=exporter.time.monotonic(),
        )

    assert process.terminated is True
    assert process.killed is False
    assert process.wait_timeouts == [10]


def test_run_command_with_progress_kills_child_after_terminate_timeout(monkeypatch):
    process = _FakeProcess(wait_timeout=True)
    monkeypatch.setattr(exporter.subprocess, "Popen", lambda *_, **__: process)
    monkeypatch.setattr(exporter, "_progress", lambda *_, **__: None)
    monkeypatch.setattr(
        exporter.time,
        "sleep",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        exporter._run_command_with_progress(
            ["fake"],
            label="notebook execution",
            progress_interval_seconds=30,
            run_started_at=exporter.time.monotonic(),
        )

    assert process.terminated is True
    assert process.killed is True
    assert process.wait_timeouts == [10, None]
