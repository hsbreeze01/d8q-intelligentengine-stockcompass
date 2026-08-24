"""Pipeline daemon single-instance lock guard (scripts/pipeline.py).

Loads scripts/pipeline.py as a standalone module (it self-inserts its
script/project dirs on sys.path before importing pipeline_config etc.),
then verifies the flock-based daemon guard semantics.
"""
import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_SCRIPT = REPO_ROOT / "scripts" / "pipeline.py"

_spec = importlib.util.spec_from_file_location("pipeline_under_test", PIPELINE_SCRIPT)
pipeline = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("pipeline_under_test", pipeline)
_spec.loader.exec_module(pipeline)


def _release(module):
    if module._daemon_lock_fd is not None:
        module._daemon_lock_fd.close()
        module._daemon_lock_fd = None


def test_first_acquire_succeeds_and_records_pid(tmp_path):
    lock_path = tmp_path / "daemon.lock"
    try:
        assert pipeline._acquire_daemon_lock(str(lock_path)) is True
        assert lock_path.read_text().strip() == str(os.getpid())
        assert pipeline._daemon_lock_fd is not None
    finally:
        _release(pipeline)


def test_second_acquire_refused_while_first_holds(tmp_path):
    lock_path = str(tmp_path / "daemon.lock")
    try:
        assert pipeline._acquire_daemon_lock(lock_path) is True
        first_fd = pipeline._daemon_lock_fd

        # Same process, second open fd => flock conflict => duplicate refused,
        # and the original holder's fd must stay untouched.
        assert pipeline._acquire_daemon_lock(lock_path) is False
        assert pipeline._daemon_lock_fd is first_fd
    finally:
        _release(pipeline)


def test_reacquire_succeeds_after_release(tmp_path):
    lock_path = str(tmp_path / "daemon.lock")
    try:
        assert pipeline._acquire_daemon_lock(str(lock_path)) is True
    finally:
        _release(pipeline)
    # Kernel dropped the flock on close: a new daemon can start cleanly.
    try:
        assert pipeline._acquire_daemon_lock(str(lock_path)) is True
    finally:
        _release(pipeline)
