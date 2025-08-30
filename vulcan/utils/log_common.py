import logging
import os
import sys
import threading
import time
from enum import Enum
from pathlib import Path

import loguru
from memoization import CachingAlgorithmFlag, cached

from vulcan.config.config import Configs
from vulcan.utils.agent_utils import Colors


def _filter_logs(record: dict) -> bool:
    # hide debug logs if Settings.basic_settings.log_verbose=False
    if record["level"].no <= 10 and not Configs.basic_config.log_verbose:
        return False
    # hide traceback logs if Settings.basic_settings.log_verbose=False
    if record["level"].no == 40 and not Configs.basic_config.log_verbose:
        record["exception"] = None
    return True


class TeeOutput:
    """
    Duplicate stdout/stderr to both terminal and log file.
    Preserves isatty() for libs like rich and prompt_toolkit.
    """

    def __init__(self, stream, log_file_path):
        self.stream = stream  # original stream (sys.__stdout__ / sys.__stderr__)
        self.log_file = open(log_file_path, "a", encoding="utf-8", buffering=1)
        self.lock = threading.Lock()

    def write(self, message):
        with self.lock:
            if hasattr(self.stream, "write"):
                self.stream.write(message)
                self.stream.flush()
            if self.log_file and not self.log_file.closed:
                self.log_file.write(message)
                self.log_file.flush()

    def flush(self):
        with self.lock:
            if hasattr(self.stream, "flush"):
                self.stream.flush()
            if self.log_file and not self.log_file.closed:
                self.log_file.flush()

    def close(self):
        with self.lock:
            if self.log_file:
                self.log_file.close()

    def isatty(self):
        return hasattr(self.stream, "isatty") and self.stream.isatty()

    def __getattr__(self, name):
        return getattr(self.stream, name)


_CURRENT_LOG_FILE_PATH = None
_LOGGING_INITIALIZED = False


def setup_logging(log_file: str = "vulcan_run.log", verbose: bool = False):
    """Configure initial unified logging."""
    global _CURRENT_LOG_FILE_PATH, _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    _CURRENT_LOG_FILE_PATH = log_file

    # redirect stdout/stderr
    sys.stdout = TeeOutput(sys.__stdout__, log_file)
    sys.stderr = TeeOutput(sys.__stderr__, log_file)

    # cấu hình loguru
    loguru.logger._core.handlers[0]._filter = _filter_logs
    logger = loguru.logger
    logger.warn = logger.warning
    if log_file:
        if not log_file.endswith(".log"):
            log_file = f"{log_file}.log"
        if not os.path.isabs(log_file):
            log_file = str((Configs.basic_config.LOG_PATH / log_file).resolve())
        logger.add(log_file, colorize=False, filter=_filter_logs)

    _LOGGING_INITIALIZED = True


def finalize_logging_with_session_id(temp_log_path: Path, final_session_dir: Path):
    """Di chuyển và đổi tên file log tạm thời vào thư mục session cuối cùng."""
    global _CURRENT_LOG_FILE_PATH
    if not _LOGGING_INITIALIZED or not _CURRENT_LOG_FILE_PATH:
        return

    # Đóng file log tạm thời hiện tại
    if isinstance(sys.stdout, TeeOutput):
        sys.stdout.close()
    if isinstance(sys.stderr, TeeOutput):
        sys.stderr.close()

    # Đặt tên cố định cho file log cuối cùng để dễ tìm
    final_log_file_name = "session_activity.log"
    final_log_file_path = final_session_dir / final_log_file_name

    try:
        # Di chuyển file log tạm (nếu nó tồn tại)
        if temp_log_path.exists():
            os.rename(temp_log_path, final_log_file_path)
        
        _CURRENT_LOG_FILE_PATH = str(final_log_file_path)

        # Mở lại stdout/stderr để trỏ đến file log cuối cùng
        sys.stdout = TeeOutput(sys.__stdout__, _CURRENT_LOG_FILE_PATH)
        sys.stderr = TeeOutput(sys.__stderr__, _CURRENT_LOG_FILE_PATH)
        
    except Exception as e:
        # Nếu có lỗi, quay lại stdout/stderr gốc để tránh mất log
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        print(f"{Colors.RED}Error finalizing log file: {e}{Colors.RESET}")