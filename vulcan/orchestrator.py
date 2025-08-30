import os
import time
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

from vulcan.agent_core.agent import create_agent
from vulcan.agent_core.environment import auto_setup
from vulcan.agent_core.system_prompts import get_continuation_prompt, get_initial_prompt
from vulcan.config.config import Configs
from vulcan.persistence.session_manager import load_or_create_session, save_session
from vulcan.utils.agent_utils import analyze_objective_completion, print_banner, create_session_dir_name
from vulcan.utils.log_common import finalize_logging_with_session_id, setup_logging

load_dotenv()
console = Console()


@click.command(help="Start a new or continue a previous penetration testing session.")
@click.option(
    "--mission", "-m", help="Full mission description, including target and objective."
)
@click.option(
    "--iterations", "-i", type=int, help="Override max iterations from config."
)
@click.option(
    "--no-parallel",
    is_flag=True,
    default=False,
    help="Forcefully disable parallel execution for all tools.",
)
@click.option(
    '--name',
    '--session-name',
    'session_name', 
    default=None,
    help='Assign a memorable name to this session for easy identification.'
)
def main(mission: str, iterations: int, no_parallel: bool, session_name: str | None):
    log_path_root = Configs.basic_config.LOG_PATH
    temp_log_file = log_path_root / f"temp_log_{int(time.time())}.log"
    setup_logging(log_file=str(temp_log_file), verbose=True)
    print_banner()

    os.environ["BYPASS_TOOL_CONSENT"] = "true"
    if no_parallel:
        os.environ["VULCAN_DISABLE_PARALLEL"] = "true"
        console.print(
            "[yellow][CONFIG] Parallel execution has been forcefully disabled by the user.[/yellow]"
        )
    else:
        os.environ.pop("VULCAN_DISABLE_PARALLEL", None)

    console.rule("[bold red]VulCan Autonomous Agent[/bold red]")

    session = load_or_create_session(
        initial_mission_prompt=mission,
        session_name=session_name
    )
    if not session:
        console.print("[red]Could not start a session. Exiting.[/red]")
        if temp_log_file.exists():
            temp_log_file.unlink()
        return

    session_dir_name = create_session_dir_name(session.name, session.id)
    session_output_dir = Path("sessions_output") / session_dir_name
    session_output_dir.mkdir(parents=True, exist_ok=True)

    finalize_logging_with_session_id(
        temp_log_path=temp_log_file,
        final_session_dir=session_output_dir
    )

    console.print(f"\n[bold]Starting Session:[/bold] [cyan]{session.name}[/cyan] (ID: [dim]{session.id}[/dim])")
    console.print(f"[bold]All outputs for this session will be saved in:[/bold] [yellow]{session_output_dir.resolve()}[/yellow]")
    console.print(f"[bold]Mission:[/bold] [yellow]{session.init_description}[/yellow]")

    max_iterations = (
        iterations if iterations is not None else Configs.basic_config.max_iterations
    )
    console.print(f"[bold]Max Steps:[/bold] {max_iterations}")

    agent = None
    try:
        available_tools = auto_setup()

        agent, callback_handler = create_agent(
            session=session,
            max_steps=max_iterations,
            available_tools=available_tools,
            session_output_dir=session_output_dir
        )
        console.print("[green]Agent Core initialized successfully.[/green]")

        initial_prompt = get_initial_prompt(
            mission_details=session.init_description,
            iterations=max_iterations,
            available_tools=available_tools,
        )

        messages = []
        current_message = initial_prompt
        console.rule("[bold blue]Agent Execution Log[/bold blue]")

        while True:
            if not messages:
                result = agent(current_message)
            else:
                result = agent(current_message, messages=messages)

            messages.append({"role": "user", "content": [{"text": current_message}]})
            if hasattr(result, "content") and isinstance(result.content, list):
                messages.append({"role": "assistant", "content": result.content})
            else:
                messages.append(
                    {"role": "assistant", "content": [{"text": str(result)}]}
                )

            is_complete, _, _ = analyze_objective_completion(messages)
            if is_complete:
                console.print(
                    "[bold green]Agent has determined the mission is complete.[/bold green]"
                )
                break

            if callback_handler and callback_handler.should_stop():
                console.print(
                    "[bold yellow]Agent stopped (step limit reached or stop tool used).[/bold yellow]"
                )
                break

            remaining_steps = max_iterations - (
                callback_handler.steps if callback_handler else 0
            )
            current_message = get_continuation_prompt(remaining_steps, max_iterations)
            time.sleep(0.5)

    except Exception as e:
        console.print(
            f"\n[bold red]A critical error occurred during agent execution: {e}[/bold red]"
        )
        import traceback

        traceback.print_exc()
    finally:
        if agent and "callback_handler" in locals() and callback_handler is not None:
            console.rule("[bold blue]Generating Final Report[/bold blue]")
            callback_handler.generate_final_report(
                agent=agent,
                target=session.init_description,
                objective="",
                session_output_dir=session_output_dir
            )

        if session:
            save_session(session)

    console.rule("[bold red]VulCan Session Finished[/bold red]")
