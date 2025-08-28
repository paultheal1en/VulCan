from typing import Optional

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import confirm
from rich.console import Console

# Import các model và repository
from .models.session_model import Session, SessionModel
from .repository.session_repository import (
    add_session_to_db,
    fetch_all_sessions,
    update_session_in_db,
)

console = Console()
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)


def load_or_create_session(
    initial_mission_prompt: Optional[str] = None,
) -> Optional[Session]:
    """
    Quản lý việc tải hoặc tạo một session mới.
    """
    if confirm("Bạn có muốn tiếp tục từ một phiên làm việc trước đó không?"):
        sessions = fetch_all_sessions()
        if not sessions:
            console.print(
                "[yellow]Không tìm thấy phiên làm việc nào. Bắt đầu một phiên mới.[/yellow]"
            )
            return _create_new_session(initial_mission_prompt)

        console.print("Vui lòng chọn phiên làm việc cũ bằng chỉ số (số nguyên):")
        for i, session_item in enumerate(sessions):
            console.print(f"{str(i)}. {session_item.name} (ID: {session_item.id})")

        try:
            selected_index = int(prompt("Nhập lựa chọn của bạn: "))
            selected_session = sessions[selected_index]
            console.print(f"Bạn đã chọn: [cyan]{selected_session.name}[/cyan]")
            return selected_session
        except (ValueError, IndexError):
            console.print("[red]Lựa chọn không hợp lệ. Bắt đầu một phiên mới.[/red]")
            return _create_new_session(initial_mission_prompt)
    else:
        return _create_new_session(initial_mission_prompt)


def _create_new_session(initial_mission_prompt: Optional[str] = None) -> Session:
    """Hàm nội bộ để tạo một session mới từ một lời nhắc duy nhất."""
    console.print("--- Starting a new session ---")

    # Nếu không có lời nhắc nào được truyền từ CLI, hãy hỏi người dùng
    if not initial_mission_prompt:
        initial_mission_prompt = prompt(
            "Please describe your penetration testing mission (including target, objective, etc.):\n> "
        )

    if not initial_mission_prompt or not initial_mission_prompt.strip():
        console.print("[red]Mission description cannot be empty. Aborting.[/red]")
        return None

    session_data = Session(
        init_description=initial_mission_prompt.strip(),
    )

    # Lưu vào DB và nhận lại session đầy đủ
    new_session = add_session_to_db(session_data=session_data)
    console.print(f"Created new session with ID: [cyan]{new_session.id}[/cyan]")
    return new_session


def save_session(session: Session):
    """Lưu lại trạng thái của session vào database."""
    console.print("--- Đang lưu lại tiến trình của phiên làm việc ---")
    if not session.name:  # Nếu session chưa có tên
        save_name = prompt(
            "Nhập tên để lưu lại phiên làm việc này (Để trống sẽ dùng timestamp): \n> "
        )
        if not save_name.strip():
            from time import time

            save_name = f"Session_{int(time())}"
        session.name = save_name

    update_session_in_db(session_data=session)
    console.print(f"Đã lưu phiên làm việc với tên: [cyan]{session.name}[/cyan]")
