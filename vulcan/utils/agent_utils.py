#!/usr/bin/env python3

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


def get_data_path(subdir=""):
    """
    Gets the absolute path to a subdirectory within the project root.
    This is robust against being called from different working directories.
    """
    project_root = Path(__file__).resolve().parents[2]

    base_path = project_root

    if subdir:
        return os.path.join(base_path, subdir)
    return str(base_path)


# ANSI color codes for terminal output
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    """Displays the VulCan project banner."""

    # ASCII ART cho VulCan
    banner_lines = [
        r"",
        r"██╗   ██╗██╗   ██╗██╗      ██████╗ █████╗ ███╗   ██╗",
        r"██║   ██║██║   ██║██║     ██╔════╝██╔══██╗████╗  ██║",
        r"██║   ██║██║   ██║██║     ██║     ███████║██╔██╗ ██║",
        r"╚██╗ ██╔╝██║   ██║██║     ██║     ██╔══██║██║╚██╗██║",
        r" ╚████╔╝ ╚██████╔╝███████╗╚██████╗██║  ██║██║ ╚████║",
        r"  ╚═══╝   ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝",
        r"",
    ]

    subtitle = "-- Metacognitive Autonomous Penetration Testing Agent --"
    author = "Cybersecurity Research Tool"

    # Tính độ rộng lớn nhất của ASCII để căn giữa
    banner_art_width = 0
    if banner_lines:
        banner_art_width = max(len(line.rstrip()) for line in banner_lines)

    # Căn giữa subtitle và author
    padding_subtitle = (banner_art_width - len(subtitle)) // 2
    padding_author = (banner_art_width - len(author)) // 2

    centered_subtitle = (" " * max(0, padding_subtitle)) + subtitle
    centered_author = (" " * max(0, padding_author)) + author

    # Kết hợp banner, subtitle và author
    full_banner = (
        "\n".join(banner_lines)
        + "\n"
        + centered_subtitle
        + "\n"
        + centered_author
        + "\n"
    )

    print("%s%s%s" % (Colors.RED, full_banner, Colors.RESET))


def print_section(title, content, color=Colors.BLUE, emoji=""):
    """Print formatted section with optional emoji"""
    print("\n%s" % ("─" * 60))
    print("%s %s%s%s%s" % (emoji, color, Colors.BOLD, title, Colors.RESET))
    print("%s" % ("─" * 60))
    print(content)


def print_status(message, status="INFO"):
    """Print status message with color coding and emojis"""
    status_config = {
        "INFO": (Colors.BLUE, "ℹ️"),
        "SUCCESS": (Colors.GREEN, "✅"),
        "WARNING": (Colors.YELLOW, "⚠️"),
        "ERROR": (Colors.RED, "❌"),
        "THINKING": (Colors.MAGENTA, "🤔"),
        "EXECUTING": (Colors.CYAN, "⚡"),
        "FOUND": (Colors.GREEN, "🎯"),
        "EVOLVING": (Colors.CYAN, "🔄"),
        "CREATING": (Colors.YELLOW, "🛠️"),
    }
    color, emoji = status_config.get(status, (Colors.BLUE, "•"))
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(
        "%s[%s]%s %s %s[%s]%s %s"
        % (
            Colors.DIM,
            timestamp,
            Colors.RESET,
            emoji,
            color,
            status,
            Colors.RESET,
            message,
        )
    )


def analyze_objective_completion(messages: List[Dict]) -> Tuple[bool, str, Dict]:
    """Check if agent has declared objective completion through self-assessment.

    Returns:
        (is_complete, summary, metadata)
    """
    if not messages:
        return False, "", {}

    # Look for explicit completion declaration - trust the agent's judgment
    for msg in reversed(messages[-5:]):  # Check last 5 messages
        if msg.get("role") == "assistant":
            content_raw = msg.get("content", "")
            if isinstance(content_raw, list) and len(content_raw) > 0:
                content = ""
                for block in content_raw:
                    if isinstance(block, dict) and "text" in block:
                        content += block["text"] + " "
                content = content.strip()
            else:
                content = str(content_raw)

            # Check for explicit objective declaration
            if "objective achieved:" in content.lower():
                match = re.search(
                    r"objective achieved:(.+?)(?:\n|$)",
                    content,
                    re.IGNORECASE | re.DOTALL,
                )
                if match:
                    summary = match.group(1).strip()

                    # Extract any confidence or completion percentage mentioned
                    confidence_match = re.search(r"(\d+)%", content)
                    confidence = (
                        int(confidence_match.group(1)) if confidence_match else 100
                    )

                    return (
                        True,
                        summary,
                        {"confidence": confidence, "agent_determined": True},
                    )
                return (
                    True,
                    "Agent declared objective complete",
                    {"confidence": 100, "agent_determined": True},
                )

            # Check for flag pattern (CTF-style flags)
            flag_match = re.search(r"FLAG\{[^}]+\}", content)
            if flag_match:
                flag = flag_match.group(0)
                # Also check for success indicators near the flag
                if any(
                    indicator in content.lower()
                    for indicator in [
                        "congratulations",
                        "success",
                        "correct",
                        "flag obtained",
                        "flag found",
                    ]
                ):
                    return (
                        True,
                        f"Flag obtained: {flag}",
                        {"confidence": 100, "flag_detected": True},
                    )

            # Check for other success indicators that might indicate completion
            success_indicators = [
                "successfully obtained flag",
                "flag obtained",
                "challenge complete",
                "challenge solved",
                "objective complete",
            ]

            for indicator in success_indicators:
                if indicator in content.lower():
                    return (
                        True,
                        f"Success indicator detected: {indicator}",
                        {"confidence": 95, "success_indicator": True},
                    )

    return False, "", {}

def sanitize_session_name(name: str) -> str:
    """
    Làm sạch tên session để sử dụng làm một phần của tên thư mục.
    - Chuyển thành chữ thường.
    - Thay thế khoảng trắng và các ký tự không an toàn bằng dấu gạch dưới.
    - Loại bỏ các dấu gạch dưới liên tiếp.
    """
    if not name:
        return "unnamed_session"
    
    sanitized = name.lower()
    sanitized = re.sub(r'[^\w\-_]', '_', sanitized)
    sanitized = re.sub(r'__+', '_', sanitized)
    sanitized = sanitized.strip('_')
    
    if not sanitized:
        return "sanitized_session"
        
    return sanitized

def create_session_dir_name(session_name: str, session_id: str) -> str:
    """
    Tạo một tên thư mục DUY NHẤT và dễ đọc bằng cách kết hợp
    tên session đã được làm sạch và một phần của ID session.
    """
    sanitized_name = sanitize_session_name(session_name)
    
    short_id = session_id
    
    # Kết hợp chúng lại, ví dụ: "my_pentest_dbe78e3e"
    final_dir_name = f"{sanitized_name}_{short_id}"
    
    # Cắt ngắn nếu tên kết hợp quá dài
    return final_dir_name
