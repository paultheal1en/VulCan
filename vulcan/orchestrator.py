import click
from rich.console import Console
import os
import time

from vulcan.config.config import Configs
from vulcan.persistence.session_manager import load_or_create_session, save_session
from vulcan.agent_core.agent import create_agent
from vulcan.agent_core.system_prompts import get_initial_prompt, get_continuation_prompt
from vulcan.agent_core.utils import analyze_objective_completion
from vulcan.agent_core.environment import auto_setup
from dotenv import load_dotenv

console = Console()

@click.command(help="Start a new or continue a previous penetration testing session.")
@click.option("--mission", "-m", help="Full mission description, including target and objective.")
@click.option("--iterations", "-i", type=int, help="Override max iterations from config.")
def main(mission: str, iterations: int):
    """Hàm chính điều phối hoạt động của VulCan."""
    load_dotenv() 
    os.environ["BYPASS_TOOL_CONSENT"] = "true"
    console.rule("[bold red]VulCan Autonomous Agent[/bold red]")

    # 1. Tải hoặc tạo session, truyền vào lời nhắc từ CLI
    session = load_or_create_session(initial_mission_prompt=mission)
    if not session:
        console.print("[red]Could not start a session. Exiting.[/red]")
        return

    console.print(f"\n[bold]Starting Session:[/bold] [cyan]{session.id}[/cyan]")
    console.print(f"[bold]Mission:[/bold] [yellow]{session.init_description}[/yellow]")
    
    max_iterations = iterations if iterations is not None else Configs.basic_config.max_iterations
    console.print(f"[bold]Max Steps:[/bold] {max_iterations}")

    agent = None
    try:
        available_tools = auto_setup()
        
        agent, callback_handler = create_agent(
            session=session,
            max_steps=max_iterations,
            available_tools=available_tools,
            has_persisted_plan=(session.current_planner_id is not None and session.current_planner_id != "")
        )
        console.print("[green]Agent Core initialized successfully.[/green]")

        initial_prompt = get_initial_prompt(
            mission_details=session.init_description, 
            iterations=max_iterations,
            available_tools=available_tools
        )
        
        messages = []
        current_message = initial_prompt
        console.rule("[bold blue]Agent Execution Log[/bold blue]")

        while True:
            # Sửa logic gọi agent để phân biệt lần đầu và các lần sau
            if not messages:
                # Lần gọi đầu tiên, không truyền messages
                result = agent(current_message)
            else:
                # Các lần sau, truyền cả messages
                result = agent(current_message, messages=messages)

            messages.append({"role": "user", "content": [{"text": current_message}]})
            if hasattr(result, 'content') and isinstance(result.content, list):
                messages.append({"role": "assistant", "content": result.content})
            else:
                messages.append({"role": "assistant", "content": [{"text": str(result)}]})
            is_complete, _, _ = analyze_objective_completion(messages)
            if is_complete:
                console.print("[bold green]Agent has determined the mission is complete.[/bold green]")
                break

            if callback_handler and callback_handler.should_stop():
                console.print("[bold yellow]Agent stopped (step limit reached or stop tool used).[/bold yellow]")
                break
            
            remaining_steps = max_iterations - (callback_handler.steps if callback_handler else 0)
            current_message = get_continuation_prompt(remaining_steps, max_iterations)
            time.sleep(0.5)

    except Exception as e:
        console.print(f"\n[bold red]A critical error occurred during agent execution: {e}[/bold red]")
        import traceback
        traceback.print_exc()
    finally:
        if agent and 'callback_handler' in locals() and callback_handler is not None:
            console.rule("[bold blue]Generating Final Report[/bold blue]")
            callback_handler.generate_final_report(agent, session.init_description, "")
        
        if session:
            save_session(session)

    console.rule("[bold red]VulCan Session Finished[/bold red]")