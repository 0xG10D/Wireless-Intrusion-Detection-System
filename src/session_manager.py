from __future__ import annotations

import atexit
import json
import os
import signal
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Callable


class SessionLockError(RuntimeError):
    """Raised when another WIDS engine already owns the session lock."""


class SessionManager:
    def __init__(self, base_dir: Path, data_dir: Path, archive_dir: Path) -> None:
        self.base_dir = base_dir
        self.data_dir = data_dir
        self.archive_dir = archive_dir
        self.runtime_dir = base_dir / "runtime"
        self.lock_path = self.runtime_dir / "wids_engine.lock"
        self.pid = os.getpid()
        self.stop_requested = False
        self._acquired = False
        self._on_stop: Callable[[str], None] | None = None
        self._on_suspend: Callable[[str], None] | None = None
        self._stop_signal_seen = False

    def acquire(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._apply_permissions(self.runtime_dir, is_dir=True)

        legacy_process = self._find_existing_engine_process()
        if legacy_process is not None:
            existing_pid, state = legacy_process
            if state == "T":
                raise SessionLockError(
                    f"WIDS engine PID {existing_pid} is stopped. Do not use CTRL+Z; use CTRL+C to stop."
                )
            raise SessionLockError(
                f"WIDS engine PID {existing_pid} is already running."
            )

        if self.lock_path.exists():
            existing_pid = self._read_lock_pid()
            if existing_pid is not None and self._process_exists(existing_pid):
                state = self._process_state(existing_pid)
                if state == "T":
                    raise SessionLockError(
                        f"WIDS engine PID {existing_pid} is stopped. Do not use CTRL+Z; use CTRL+C to stop."
                    )
                raise SessionLockError(
                    f"WIDS engine PID {existing_pid} is already running."
                )
            self.lock_path.unlink(missing_ok=True)

        payload = {
            "pid": self.pid,
            "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "cwd": str(self.base_dir),
        }
        with self.lock_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        self._apply_permissions(self.lock_path)

        self._acquired = True
        atexit.register(self.release)

    def release(self) -> None:
        if not self._acquired:
            return

        try:
            if self.lock_path.exists():
                lock_pid = self._read_lock_pid()
                if lock_pid in {None, self.pid}:
                    self.lock_path.unlink(missing_ok=True)
        finally:
            self._acquired = False

    def install_signal_handlers(
        self,
        on_stop: Callable[[str], None] | None = None,
        on_suspend: Callable[[str], None] | None = None,
    ) -> None:
        self._on_stop = on_stop
        self._on_suspend = on_suspend

        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, self._handle_stop_signal)

        if hasattr(signal, "SIGTSTP"):
            signal.signal(signal.SIGTSTP, self._handle_suspend_signal)

    def archive_data_dir(self) -> Path | None:
        if not self.data_dir.exists():
            return None

        data_entries = [item for item in self.data_dir.iterdir()]
        if not data_entries:
            return None

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._apply_permissions(self.archive_dir, is_dir=True)

        archive_name = f"session_{datetime.now().strftime('%Y%m%dT%H%M%S')}.tar.gz"
        archive_path = self.archive_dir / archive_name
        with tarfile.open(archive_path, "w:gz") as archive_handle:
            for item in data_entries:
                archive_handle.add(item, arcname=f"data/{item.name}")
        self._apply_permissions(archive_path)
        return archive_path

    def _handle_stop_signal(self, signum: int, _frame: object) -> None:
        self.stop_requested = True
        if self._stop_signal_seen:
            return
        self._stop_signal_seen = True

        signal_name = signal.Signals(signum).name
        message = f"Stop signal received ({signal_name}). Shutting down WIDS engine cleanly."
        if self._on_stop is not None:
            self._on_stop(message)

    def _handle_suspend_signal(self, _signum: int, _frame: object) -> None:
        message = "Do not use CTRL+Z; use CTRL+C to stop."
        if self._on_suspend is not None:
            self._on_suspend(message)
        else:
            print(message, flush=True)

    def _read_lock_pid(self) -> int | None:
        try:
            with self.lock_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

        try:
            return int(payload.get("pid"))
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _process_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    @staticmethod
    def _process_state(pid: int) -> str:
        status_path = Path("/proc") / str(pid) / "status"
        if not status_path.exists():
            return ""
        try:
            with status_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("State:"):
                        return line.split(":", 1)[1].strip().split(" ", 1)[0]
        except OSError:
            return ""
        return ""

    def _find_existing_engine_process(self) -> tuple[int, str] | None:
        proc_root = Path("/proc")
        if not proc_root.exists():
            return None

        for proc_dir in proc_root.iterdir():
            if not proc_dir.name.isdigit():
                continue
            pid = int(proc_dir.name)
            if pid == self.pid:
                continue

            cmdline_path = proc_dir / "cmdline"
            cwd_path = proc_dir / "cwd"
            try:
                cmdline = cmdline_path.read_text(encoding="utf-8").replace("\x00", " ")
                cwd = cwd_path.resolve()
            except OSError:
                continue

            if cwd != self.base_dir:
                continue
            if "main.py" not in cmdline:
                continue

            return pid, self._process_state(pid)

        return None

    @staticmethod
    def _apply_permissions(path: Path, is_dir: bool = False) -> None:
        try:
            mode = 0o775 if is_dir else 0o664
            os.chmod(path, mode)
        except OSError:
            pass

        sudo_uid = os.environ.get("SUDO_UID")
        sudo_gid = os.environ.get("SUDO_GID")
        if sudo_uid is None or sudo_gid is None:
            return
        if not hasattr(os, "chown"):
            return

        try:
            os.chown(path, int(sudo_uid), int(sudo_gid))
        except (OSError, ValueError):
            pass
