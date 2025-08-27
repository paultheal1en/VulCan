#!/usr/bin/env python3

import logging
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from vulcan.utils.agent_utils import Colors, get_data_path


def clean_operation_memory(operation_id: str) -> None:
    """Clean up memory data for a specific operation."""
    mem0_path = f"/tmp/mem0_{operation_id}"
    if os.path.exists(mem0_path):
        try:
            shutil.rmtree(mem0_path)
            print(f"{Colors.GREEN}[*] Cleaned up operation memory: {mem0_path}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Failed to clean {mem0_path}: {str(e)}{Colors.RESET}")


def auto_setup(skip_mem0_cleanup: bool = False) -> List[str]:
    """Setup directories and discover available cyber tools."""
    # Create necessary directories
    Path("tools").mkdir(exist_ok=True)
    Path(get_data_path("logs")).mkdir(exist_ok=True)

    if skip_mem0_cleanup:
        print(f"{Colors.CYAN}[*] Using existing memory store{Colors.RESET}")

    print(f"{Colors.CYAN}[*] Discovering cyber security tools...{Colors.RESET}")

    cyber_tools = {
        "nuclei": "Fast, template-based vulnerability scanner",
        "subfinder": "Subdomain discovery tool",
        "httpx": "Fast HTTP probe to check for live web servers",
        "katana": "Web crawler and spider",
        "ffuf": "Fast web fuzzer for directory/file discovery",
        "arjun": "HTTP parameter discovery suite",
        "nmap": "Network discovery and security auditing",
        "nikto": "Web server scanner",
        "sqlmap": "SQL injection detection and exploitation",
        "gobuster": "Directory/file brute-forcer",
        "netcat": "Network utility for reading/writing data",
        "curl": "HTTP client for web requests",
        "metasploit": "Penetration testing framework",
    }

    available_tools = []

    for tool_name, description in cyber_tools.items():
        check_cmd = (
            ["which", tool_name]
            if tool_name != "metasploit"
            else ["which", "msfconsole"]
        )
        try:
            subprocess.run(check_cmd, capture_output=True, check=True, timeout=5)
            available_tools.append(tool_name)
            print(f"  {Colors.GREEN}✓{Colors.RESET} {tool_name:<12} - {description}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            print(f"  {Colors.YELLOW}○{Colors.RESET} {tool_name:<12} - {description} {Colors.DIM}(not available){Colors.RESET}")

    print(f"\n{Colors.GREEN}[+] Environment ready. {len(available_tools)} cyber tools available.{Colors.RESET}\n")

    return available_tools


class TeeOutput:
    """Thread-safe output duplicator to both terminal and log file."""

    def __init__(self, stream, log_file: str):
        self.terminal = stream
        self.log = open(log_file, "a", encoding="utf-8", buffering=1)  # Line buffering
        self.lock = threading.Lock()

    def write(self, message: str) -> None:
        with self.lock:
            self.terminal.write(message)
            self.terminal.flush()
            try:
                self.log.write(message)
                self.log.flush()
            except (ValueError, OSError):
                pass  # Handle closed file gracefully

    def flush(self) -> None:
        with self.lock:
            self.terminal.flush()
            try:
                self.log.flush()
            except (ValueError, OSError):
                pass

    def close(self) -> None:
        with self.lock:
            try:
                self.log.close()
            except Exception:
                pass

    def fileno(self) -> int:
        return self.terminal.fileno()

    def isatty(self) -> bool:
        return self.terminal.isatty()


def setup_logging(log_file: str = "cyber_operations.log", verbose: bool = False) -> logging.Logger:
    """Configure unified logging for all operations with complete terminal capture."""
    # Ensure the directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create header in log file
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"VulCan SESSION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

    # Set up stdout and stderr redirection
    sys.stdout = TeeOutput(sys.stdout, log_file)
    sys.stderr = TeeOutput(sys.stderr, log_file)

    # Formatter for logs
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File handler - log everything to file
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler - show warnings and above unless verbose
    console_handler = logging.StreamHandler(sys.__stdout__)  # Use original stdout
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)

    # Configure VulCan logger
    cyber_logger = logging.getLogger("VulCan")
    cyber_logger.setLevel(logging.DEBUG)
    cyber_logger.addHandler(file_handler)
    if verbose:
        cyber_logger.addHandler(console_handler)
    cyber_logger.propagate = False

    # Suppress Strands framework error logging for expected step limit termination
    strands_event_loop_logger = logging.getLogger("strands.event_loop.event_loop")
    strands_event_loop_logger.setLevel(logging.CRITICAL)

    # Capture all other loggers at INFO level to file
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_file_handler = logging.FileHandler(log_file, mode="a")
    root_file_handler.setLevel(logging.INFO)
    root_file_handler.setFormatter(formatter)
    root_logger.addHandler(root_file_handler)

    return cyber_logger