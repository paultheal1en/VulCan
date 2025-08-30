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
import time

warnings.filterwarnings("ignore", category=DeprecationWarning)


def load_or_create_session(
    initial_mission_prompt: Optional[str] = None,
    session_name: Optional[str] = None,
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
            return _create_new_session(initial_mission_prompt, session_name)

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
            return _create_new_session(initial_mission_prompt, session_name)
    else:
        return _create_new_session(initial_mission_prompt, session_name)


def _create_new_session(
    initial_mission_prompt: Optional[str] = None,
    session_name: Optional[str] = None
) -> Session:
    """Hàm nội bộ để tạo một session mới, xử lý cả luồng tương tác và không tương tác."""
    console.print("--- Starting a new session ---")

    final_mission_prompt = initial_mission_prompt
    if not final_mission_prompt or not final_mission_prompt.strip():
        final_mission_prompt = prompt(
            "Please describe your penetration testing mission (including target, objective, etc.):\n> "
        )

    if not final_mission_prompt or not final_mission_prompt.strip():
        console.print("[red]Mission description cannot be empty. Aborting.[/red]")
        return None

    final_session_name = session_name

    if not final_session_name or not final_session_name.strip():
        final_session_name = prompt(
            "Enter a name for this session (leave blank for default): \n> "
        )

    if not final_session_name or not final_session_name.strip():
        timestamp = int(time.time())
        final_session_name = f"Session_{timestamp}"
        console.print(f"No session name provided. Using default: [yellow]{final_session_name}[/yellow]")

    session_data = Session(
        init_description=final_mission_prompt.strip(),
        name=final_session_name.strip()
    )

    new_session = add_session_to_db(session_data=session_data)
    console.print(f"Created new session '[cyan]{new_session.name}[/cyan]' with ID: [dim]{new_session.id}[/dim]")
    return new_session


def save_session(session: Session):
    """Lưu lại trạng thái của session vào database."""
    console.print("--- Đang lưu lại tiến trình của phiên làm việc ---")
    if not session.name or not session.name.strip():  # Nếu session chưa có tên
        save_name = prompt(
            "Nhập tên để lưu lại phiên làm việc này (Để trống sẽ dùng timestamp): \n> "
        )
        if not save_name.strip():
            from time import time

            save_name = f"Session_{int(time())}"
        session.name = save_name

    update_session_in_db(session_data=session)
    console.print(f"Đã lưu phiên làm việc với tên: [cyan]{session.name}[/cyan]")
