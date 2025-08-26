import sys
import os
import time
import threading
import logging
from enum import Enum
from pathlib import Path

import loguru
from memoization import cached, CachingAlgorithmFlag

from vulcan.config.config import Configs
from vulcan.agent_core.utils import Colors  # chỉnh lại path nếu cần

# ===========================
# RoleType enum
# ===========================
class RoleType(Enum):
    COLLECTOR = "Collection"
    SCANNER = "Scanning"
    EXPLOITER = "Exploitation"


# ===========================
# Log filter
# ===========================
def _filter_logs(record: dict) -> bool:
    # hide debug logs if Settings.basic_settings.log_verbose=False
    if record["level"].no <= 10 and not Configs.basic_config.log_verbose:
        return False
    # hide traceback logs if Settings.basic_settings.log_verbose=False
    if record["level"].no == 40 and not Configs.basic_config.log_verbose:
        record["exception"] = None
    return True


# ===========================
# TeeOutput để redirect stdout/stderr
# ===========================
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


# ===========================
# Biến toàn cục
# ===========================
_CURRENT_LOG_FILE_PATH = None
_LOGGING_INITIALIZED = False


# ===========================
# setup_logging
# ===========================
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


# ===========================
# finalize_logging_with_session_id
# ===========================
def finalize_logging_with_session_id(log_path: Path, session_id: str):
    """Renames the temporary log file to its final name using the session ID."""
    global _CURRENT_LOG_FILE_PATH
    if not _LOGGING_INITIALIZED or not _CURRENT_LOG_FILE_PATH:
        return

    if isinstance(sys.stdout, TeeOutput):
        sys.stdout.close()
    if isinstance(sys.stderr, TeeOutput):
        sys.stderr.close()

    final_log_file_name = f"session_{session_id}.log"
    final_log_file_path = log_path / final_log_file_name

    try:
        os.rename(_CURRENT_LOG_FILE_PATH, final_log_file_path)
        _CURRENT_LOG_FILE_PATH = str(final_log_file_path)

        sys.stdout = TeeOutput(sys.__stdout__, _CURRENT_LOG_FILE_PATH)
        sys.stderr = TeeOutput(sys.__stderr__, _CURRENT_LOG_FILE_PATH)

        print(f"{Colors.GREEN}Logging session to: {_CURRENT_LOG_FILE_PATH}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}Error finalizing log file: {e}{Colors.RESET}")
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
# ===========================
# Legacy helpers
# ===========================
def get_timestamp_ms():
    return int(round(time.time() * 1000))


def get_log_file(log_path: str, sub_dir: str):
    """sub_dir should contain a timestamp."""
    log_dir = os.path.join(log_path, sub_dir)
    os.makedirs(log_dir, exist_ok=False)
    return os.path.join(log_dir, f"{sub_dir}.log")


class LoggerNameFilter(logging.Filter):
    def filter(self, record):
        return True


def get_config_dict(
    log_level: str, log_file_path: str, log_backup_count: int, log_max_bytes: int
) -> dict:
    log_file_path = (
        log_file_path.encode("unicode-escape").decode()
        if os.name == "nt"
        else log_file_path
    )
    log_level = log_level.upper()
    config_dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "formatter": {
                "format": (
                    "%(asctime)s %(name)-12s %(process)d %(levelname)-8s %(message)s"
                )
            },
        },
        "filters": {
            "logger_name_filter": {
                "()": __name__ + ".LoggerNameFilter",
            },
        },
        "handlers": {
            "stream_handler": {
                "class": "logging.StreamHandler",
                "formatter": "formatter",
                "level": log_level,
            },
            "file_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "formatter",
                "level": log_level,
                "filename": log_file_path,
                "mode": "a",
                "maxBytes": log_max_bytes,
                "backupCount": log_backup_count,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "chatchat_core": {
                "handlers": ["stream_handler", "file_handler"],
                "level": log_level,
                "propagate": False,
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["stream_handler", "file_handler"],
        },
    }
    return config_dict
