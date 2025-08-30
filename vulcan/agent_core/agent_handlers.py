#!/usr/bin/env python3

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List
from pathlib import Path

from rich.console import Console
from strands import Agent
from strands.handlers import PrintingCallbackHandler

from vulcan.utils.agent_utils import Colors, get_data_path

from .memory_tools import get_memory_client

console = Console()
logger = logging.getLogger("VulCan.handlers")

# Constants for display formatting
CONTENT_PREVIEW_LENGTH = 150
METADATA_PREVIEW_LENGTH = 100
MAX_TOOL_CODE_LINES = 100
EVIDENCE_PREVIEW_LENGTH = 80
FALLBACK_EVIDENCE_PREVIEW_LENGTH = 200


class ReasoningHandler(PrintingCallbackHandler):
    """Callback handler for cyber security assessment operations with step tracking and reporting."""

    def __init__(self, max_steps: int = 100, operation_id: str = None):
        super().__init__()
        self.current_reasoning_buffer = ""
        self.reasoning_header_printed = False
        self.steps = 0
        self.max_steps = max_steps
        self.memory_operations = 0
        self.created_tools: List[str] = []
        self.tools_used: List[str] = []
        self.tool_effectiveness: Dict[str, Dict[str, int]] = {}
        self.last_was_reasoning = False
        self.last_was_tool = False
        self.shown_tools: set = set()  # Track shown tools to avoid duplicates
        self.tool_use_map: Dict[str, Dict] = {}  # Map tool IDs to tool info
        self.tool_results: Dict[str, Dict] = {}  # Store tool results for output display
        self.suppress_parent_output = False  # Flag to control parent handler
        self.step_limit_reached = False  # Flag to track if we've hit the limit
        self.stop_tool_used = False  # Flag to track if stop tool was used
        self.report_generated = False  # Flag to prevent duplicate reports

        # Use provided operation ID or generate one
        self.operation_id = (
            operation_id or f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Print header
        self._print_separator()
        print(f"🔐 {Colors.CYAN}{Colors.BOLD}Cyber Security Assessment{Colors.RESET}")
        print(f"   Operation: {Colors.DIM}{self.operation_id}{Colors.RESET}")
        print(f"   Started:   {Colors.DIM}{timestamp}{Colors.RESET}")
        self._print_separator()

    def _print_separator(self) -> None:
        print(f"\n\r{Colors.DIM}{'─' * 80}{Colors.RESET}\n\r", end="")

    def __call__(self, **kwargs):
        # Immediately return if step limit has been reached
        if self.step_limit_reached:
            return

        # Handle streaming text data (reasoning/thinking)
        if "data" in kwargs:
            text = kwargs.get("data", "")
            self._handle_text_block(text)
            return

        # Handle message events (tool uses and results)
        if "message" in kwargs:
            message = kwargs["message"]
            if isinstance(message, dict):
                content = message.get("content", [])
                # Handle text blocks (reasoning)
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        self._handle_text_block(text)

                # Process tool uses
                for block in content:
                    if isinstance(block, dict) and "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_id = tool_use.get("toolUseId", "")
                        if tool_id not in self.shown_tools:
                            tool_input = tool_use.get("input", {})
                            if self._is_valid_tool_use(
                                tool_use.get("name", ""), tool_input
                            ):
                                self.shown_tools.add(tool_id)
                                self.tool_use_map[tool_id] = tool_use
                                self._show_tool_execution(tool_use)
                                self.last_was_tool = True
                                self.last_was_reasoning = False

                # Process tool results
                for block in content:
                    if isinstance(block, dict) and "toolResult" in block:
                        tool_result = block["toolResult"]
                        tool_id = tool_result.get("toolUseId", "")
                        if tool_id in self.tool_use_map:
                            self.tool_results[tool_id] = tool_result
                            self._show_tool_result(tool_id, tool_result)
                            self._track_tool_effectiveness(tool_id, tool_result)
                            # Track memory operations
                            tool_name = self.tool_use_map[tool_id].get("name", "")
                            if (
                                tool_name == "mem0_memory"
                                and self.tool_use_map[tool_id]
                                .get("input", {})
                                .get("action")
                                == "store"
                            ):
                                self.memory_operations += 1

                # Prevent duplicate output from parent handler
                self.suppress_parent_output = True
                return

        # Handle tool usage announcement from streaming
        if "current_tool_use" in kwargs:
            if self.step_limit_reached:
                return
            tool = kwargs["current_tool_use"]
            tool_id = tool.get("toolUseId", "")
            tool_input = tool.get("input", {})
            if (
                self._is_valid_tool_use(tool.get("name", ""), tool_input)
                and tool_id not in self.shown_tools
            ):
                self.shown_tools.add(tool_id)
                self.tool_use_map[tool_id] = tool
                self._show_tool_execution(tool)
                self.last_was_tool = True
                self.last_was_reasoning = False
            return

        # Handle tool result events
        if "toolResult" in kwargs:
            tool_result = kwargs["toolResult"]
            tool_id = tool_result.get("toolUseId", "")
            if tool_id in self.tool_use_map:
                self._show_tool_result(tool_id, tool_result)
                self._track_tool_effectiveness(tool_id, tool_result)
            return

        # For lifecycle events, pass to parent but respect suppression flag
        if any(
            k in kwargs
            for k in [
                "init_event_loop",
                "start_event_loop",
                "start",
                "complete",
                "force_stop",
            ]
        ):
            if not self.suppress_parent_output:
                super().__call__(**kwargs)
            return

    def _is_valid_tool_use(self, tool_name: str, tool_input: any) -> bool:
        """Check if this tool use has valid input (not empty)."""
        if not tool_input or not isinstance(tool_input, dict):
            return False

        if tool_name == "shell":
            command = tool_input.get("command", "")
            if isinstance(command, list):
                command = " ".join(command) if command else ""
            return bool(command.strip() if isinstance(command, str) else command)
        elif tool_name == "mem0_memory":
            action = tool_input.get("action", "")
            if action == "store":
                content = tool_input.get("content", "")
                return bool(content.strip() if isinstance(content, str) else content)
            elif action == "retrieve":
                query = tool_input.get("query", "")
                return bool(query.strip() if isinstance(query, str) else query)
            elif action in ["list", "delete", "get", "history"]:
                return True
            return False
        elif tool_name == "file_write":
            return bool(tool_input.get("path") and tool_input.get("content"))
        elif tool_name == "editor":
            return bool(tool_input.get("command") and tool_input.get("path"))
        elif tool_name == "load_tool":
            path = tool_input.get("path", "")
            return bool(path.strip() if isinstance(path, str) else path)
        return bool(tool_input)

    def _handle_text_block(self, text: str) -> None:
        """Accumulate, clean, and print agent thoughts with highlighted formatting, handling streaming."""
        self.current_reasoning_buffer += text.replace("\r", "")

        while "\n" in self.current_reasoning_buffer:
            line, self.current_reasoning_buffer = self.current_reasoning_buffer.split(
                "\n", 1
            )
            if not line.strip():
                continue

            if not self.reasoning_header_printed:
                if self.last_was_tool:
                    print()
                print(
                    f"{Colors.MAGENTA}╭─ 🤔 Agent Reasoning {'─' * (80 - 20)}{Colors.RESET}"
                )
                self.reasoning_header_printed = True
                self.last_was_tool = False

            print(
                f"{Colors.MAGENTA}│{Colors.RESET}  {Colors.DIM}{line.lstrip()}{Colors.RESET}"
            )
            self.last_was_reasoning = True

    def _show_tool_execution(self, tool_use: Dict) -> None:
        """Display tool execution with clean formatting."""
        # Handle any remaining reasoning buffer
        if self.current_reasoning_buffer:
            remaining_line = self.current_reasoning_buffer
            self.current_reasoning_buffer = ""
            if not self.reasoning_header_printed:
                if self.last_was_tool:
                    print()
                print(
                    f"{Colors.MAGENTA}╭─ 🤔 Agent Reasoning {'─' * (80 - 20)}{Colors.RESET}"
                )
                self.reasoning_header_printed = True
                self.last_was_tool = False
            print(
                f"{Colors.MAGENTA}│{Colors.RESET}  {Colors.DIM}{remaining_line.lstrip()}{Colors.RESET}"
            )
            self.last_was_reasoning = True

        if self.reasoning_header_printed:
            print(f"{Colors.MAGENTA}╰{'─' * (80 - 1)}{Colors.RESET}")
            self.reasoning_header_printed = False

        # Check step limit
        if self.steps >= self.max_steps and not self.step_limit_reached:
            self.step_limit_reached = True
            print(
                f"\n{Colors.BLUE}Step limit reached ({self.max_steps}). Assessment complete.{Colors.RESET}"
            )
            raise StopIteration("Step limit reached - clean termination")

        self.steps += 1
        tool_name = tool_use.get("name", "unknown")
        tool_input = (
            tool_use.get("input", {})
            if isinstance(tool_use.get("input", {}), dict)
            else {}
        )

        if self.last_was_reasoning:
            print()

        self._print_separator()
        print(
            f"Step {self.steps}/{self.max_steps}: {Colors.CYAN}{tool_name}{Colors.RESET}"
        )
        self._print_separator()

        # Tool-specific display logic
        if tool_name == "shell":
            self._display_shell_tool(tool_input)
        elif tool_name == "file_write":
            self._display_file_write_tool(tool_input)
        elif tool_name == "editor":
            self._display_editor_tool(tool_input)
        elif tool_name == "load_tool":
            self._display_load_tool(tool_input)
        elif tool_name == "stop":
            self._display_stop_tool(tool_input)
        elif tool_name == "mem0_memory":
            self._display_mem0_memory_tool(tool_input)
        elif tool_name == "swarm":
            self._display_swarm_tool(tool_input)
        elif tool_name == "http_request":
            self._display_http_request_tool(tool_input)
        elif tool_name == "think":
            self._display_think_tool(tool_input)
        else:
            self._display_generic_tool(tool_name, tool_input)

        print()
        self.last_was_tool = True
        self.last_was_reasoning = False

    def _display_shell_tool(self, tool_input: Dict) -> None:
        is_parallel_disabled = (
            os.environ.get("VULCAN_DISABLE_PARALLEL", "false").lower() == "true"
        )
        is_parallel_requested = tool_input.get("parallel", False)
        if is_parallel_disabled and is_parallel_requested:
            print(
                f"{Colors.YELLOW}[NOTICE] User disabled parallel execution. Running commands sequentially.{Colors.RESET}"
            )
            tool_input["parallel"] = False
        command = tool_input.get("command", "")
        parallel = tool_input.get("parallel", False)
        mode = "parallel" if parallel else "sequential"

        if isinstance(command, list):
            seen = set()
            unique_commands = [
                (cmd, str(cmd))
                for cmd in command
                if (str_cmd := str(cmd)) not in seen and not seen.add(str_cmd)
            ]
            num_unique = len(unique_commands)
            duplicates_removed = len(command) - num_unique
            print(
                f"\n↳ Executing {num_unique} unique commands ({mode}) [{duplicates_removed} duplicates removed]:"
                if duplicates_removed
                else f"\n↳ Executing {num_unique} commands ({mode}):"
            )
            for i, (_, cmd_str) in enumerate(unique_commands):
                print(
                    f"                                    {i+1}. {Colors.GREEN}{cmd_str}{Colors.RESET}"
                )
            self.tools_used.append(f"shell: {num_unique} commands ({mode})")
        else:
            print(f"\n↳ Running: {Colors.GREEN}{command}{Colors.RESET}")
            self.tools_used.append(f"shell: {command}")

    def _display_file_write_tool(self, tool_input: Dict) -> None:
        path = tool_input.get("path", "")
        content_preview = str(tool_input.get("content", ""))[:50]
        print(f"\n↳ Writing: {Colors.YELLOW}{path}{Colors.RESET}")
        if content_preview:
            print(f"  Content: {Colors.DIM}{content_preview}...{Colors.RESET}")
        if path.startswith("tools/"):
            self.created_tools.append(path.replace("tools/", "").replace(".py", ""))
        self.tools_used.append(f"file_write: {path}")

    def _display_editor_tool(self, tool_input: Dict) -> None:
        command = tool_input.get("command", "")
        path = tool_input.get("path", "")
        file_text = tool_input.get("file_text", "")
        print(f"\n↳ Editor: {Colors.CYAN}{command}{Colors.RESET}")
        print(f"  Path: {Colors.YELLOW}{path}{Colors.RESET}")
        if command == "create" and file_text:
            if path.startswith("tools/") and path.endswith(".py"):
                self.created_tools.append(path.replace("tools/", "").replace(".py", ""))
                header = f"📄 {Colors.YELLOW}META-TOOL CODE:{Colors.RESET}"
            else:
                header = f"📄 {Colors.CYAN}FILE CONTENT:{Colors.RESET}"
            self._print_separator()
            print(header)
            self._print_separator()
            lines = file_text.split("\n")
            for i, line in enumerate(lines[:MAX_TOOL_CODE_LINES]):
                if path.endswith(".py"):
                    if line.strip().startswith("@tool"):
                        print(f"{Colors.GREEN}{line}{Colors.RESET}")
                    elif line.strip().startswith("def "):
                        print(f"{Colors.CYAN}{line}{Colors.RESET}")
                    elif line.strip().startswith("#"):
                        print(f"{Colors.DIM}{line}{Colors.RESET}")
                    elif line.strip().startswith(("import ", "from ")):
                        print(f"{Colors.MAGENTA}{line}{Colors.RESET}")
                    else:
                        print(line)
                else:
                    print(line)
            if len(lines) > MAX_TOOL_CODE_LINES:
                print(
                    f"{Colors.DIM}... ({len(lines) - MAX_TOOL_CODE_LINES} more lines){Colors.RESET}"
                )
            self._print_separator()
        self.tools_used.append(f"editor: {command} {path}")

    def _display_load_tool(self, tool_input: Dict) -> None:
        path = tool_input.get("path", "")
        print(f"\n↳ Loading: {Colors.GREEN}{path}{Colors.RESET}")
        self.tools_used.append(f"load_tool: {path}")

    def _display_stop_tool(self, tool_input: Dict) -> None:
        reason = tool_input.get("reason", "No reason provided")
        print(f"\n↳ Stopping: {Colors.RED}{reason}{Colors.RESET}")
        self.stop_tool_used = True
        self.tools_used.append(f"stop: {reason}")

    def _display_mem0_memory_tool(self, tool_input: Dict) -> None:
        action = tool_input.get("action", "")
        if action == "store":
            content = str(tool_input.get("content", ""))[:CONTENT_PREVIEW_LENGTH]
            metadata = tool_input.get("metadata", {})
            category = metadata.get("category", "general") if metadata else "general"
            print(
                f"\n↳ Storing [{Colors.CYAN}{category}{Colors.RESET}]: {Colors.DIM}{content}{'...' if len(str(tool_input.get('content', ''))) > CONTENT_PREVIEW_LENGTH else ''}{Colors.RESET}"
            )
            if metadata:
                print(
                    f"                          Metadata: {Colors.DIM}{str(metadata)[:METADATA_PREVIEW_LENGTH]}{'...' if len(str(metadata)) > METADATA_PREVIEW_LENGTH else ''}{Colors.RESET}"
                )
        elif action == "retrieve":
            query = tool_input.get("query", "")
            print(f'\n↳ Searching: {Colors.CYAN}"{query}"{Colors.RESET}')
        elif action == "list":
            print("\n↳ Listing evidence")
        elif action == "delete":
            memory_id = tool_input.get("memory_id", "unknown")
            print(f"\n↳ Deleting memory: {Colors.RED}{memory_id}{Colors.RESET}")
        elif action == "get":
            memory_id = tool_input.get("memory_id", "unknown")
            print(f"\n↳ Getting memory: {Colors.CYAN}{memory_id}{Colors.RESET}")
        elif action == "history":
            memory_id = tool_input.get("memory_id", "unknown")
            print(f"\n↳ Getting history for: {Colors.CYAN}{memory_id}{Colors.RESET}")
        self.tools_used.append(f"mem0_memory: {action}")

    def _display_swarm_tool(self, tool_input: Dict) -> None:
        task = tool_input.get("task", "")
        swarm_size = tool_input.get("swarm_size", 1)
        pattern = tool_input.get("coordination_pattern", "collaborative")
        tools = tool_input.get("tools", [])
        model_provider = tool_input.get("model_provider", "default")
        print(f"\n↳ {Colors.BOLD}Orchestrating Swarm Intelligence{Colors.RESET}")
        task_parts = task.split(". ")
        if len(task_parts) >= 4 and any(
            keyword in task
            for keyword in ["Objective:", "Scope:", "Success:", "Context:"]
        ):
            for part in task_parts:
                if part.strip():
                    if "Objective:" in part:
                        print(
                            f"  {Colors.CYAN}Objective:{Colors.RESET} {part.replace('Objective:', '').strip()}"
                        )
                    elif "Scope:" in part:
                        print(
                            f"  {Colors.YELLOW}Scope:{Colors.RESET} {part.replace('Scope:', '').strip()}"
                        )
                    elif "Success:" in part:
                        print(
                            f"  {Colors.GREEN}Success:{Colors.RESET} {part.replace('Success:', '').strip()}"
                        )
                    elif "Context:" in part:
                        print(
                            f"  {Colors.DIM}Context:{Colors.RESET} {part.replace('Context:', '').strip()}"
                        )
        else:
            print(
                f"  Task: {Colors.YELLOW}{task[:200] + '...' if len(task) > 200 else task}{Colors.RESET}"
            )
        print(f"  {Colors.BOLD}Configuration:{Colors.RESET}")
        print(f"    Agents: {Colors.CYAN}{int(swarm_size)}{Colors.RESET}")
        print(f"    Pattern: {Colors.MAGENTA}{pattern}{Colors.RESET}")
        if tools:
            print(
                f"    Tools: {Colors.GREEN}{', '.join(tools) if isinstance(tools, list) else str(tools)}{Colors.RESET}"
            )
        if model_provider and model_provider != "default":
            print(f"    Model: {Colors.BLUE}{model_provider}{Colors.RESET}")
        self.tools_used.append(f"swarm: {int(swarm_size)} agents, {pattern}")

    def _display_http_request_tool(self, tool_input: Dict) -> None:
        method = tool_input.get("method", "GET")
        url = tool_input.get("url", "")
        print(f"\n↳ HTTP Request: {Colors.MAGENTA}{method} {url}{Colors.RESET}")
        self.tools_used.append(f"http_request: {method} {url}")

    def _display_think_tool(self, tool_input: Dict) -> None:
        thought = tool_input.get("thought", "")
        cycle_count = tool_input.get("cycle_count", 1)
        print(f"\n↳ Thinking ({Colors.CYAN}{cycle_count} cycles{Colors.RESET}):")
        print(
            f"  Thought: {Colors.DIM}{thought[:500] + '...' if len(thought) > 500 else thought}{Colors.RESET}"
        )
        self.tools_used.append(f"think: {cycle_count} cycles")

    def _display_generic_tool(self, tool_name: str, tool_input: Dict) -> None:
        if tool_input:
            key_params = list(tool_input.keys())[:2]
            if key_params:
                params_str = ", ".join(
                    f"{k}={str(tool_input[k])[:50]}{'...' if len(str(tool_input[k])) > 50 else ''}"
                    for k in key_params
                )
                print(f"\n↳ Parameters: {Colors.DIM}{params_str}{Colors.RESET}")
            else:
                print(f"\n↳ Executing: {Colors.MAGENTA}{tool_name}{Colors.RESET}")
            self.tools_used.append(f"{tool_name}: {list(tool_input.keys())}")
        else:
            print(f"\n↳ Executing: {Colors.MAGENTA}{tool_name}{Colors.RESET}")
            self.tools_used.append(f"{tool_name}: no params")

    def _show_tool_result(self, tool_id: str, tool_result: Dict) -> None:
        """Display tool execution results if they contain meaningful output."""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")
        result_content = tool_result.get("content", [])
        status = tool_result.get("status", "unknown")

        if tool_name == "shell" and result_content:
            self._display_shell_result(result_content, status)
        elif status == "error":
            self._display_error_result(result_content)
        elif result_content and tool_name != "shell":
            self._display_generic_result(tool_name, result_content)

        self._print_separator()

    def _display_shell_result(self, result_content: List[Dict], status: str) -> None:
        full_output_text = "\n".join(
            content_block.get("text", "")
            for content_block in result_content
            if isinstance(content_block, dict) and "text" in content_block
        )
        if full_output_text.strip():
            lines = full_output_text.split("\n")
            filtered_lines = []
            in_output_section = False
            current_command_status = None
            skip_summary = False

            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith(("Error: Command:", "Command:")):
                    in_output_section = False
                    current_command_status = None
                    continue
                if line_stripped.startswith("Status:"):
                    current_command_status = line_stripped.split(":", 1)[1].strip()
                    continue
                if line_stripped.startswith("Exit Code:"):
                    continue
                if line_stripped.startswith("Output:"):
                    in_output_section = True
                    continue
                if in_output_section and (
                    line_stripped == ""
                    or line_stripped.startswith(("Error:", "Command:"))
                ):
                    in_output_section = False
                if "Execution Summary:" in line:
                    skip_summary = True
                    continue
                if skip_summary and (
                    "Total commands:" in line
                    or "Successful:" in line
                    or "Failed:" in line
                ):
                    continue
                if skip_summary and line_stripped == "":
                    skip_summary = False
                    continue
                if in_output_section or (
                    current_command_status == "error" and line_stripped
                ):
                    filtered_lines.append(line)

            cleaned_output = "\n".join(filtered_lines).strip()
            if cleaned_output:
                color = (
                    Colors.RED
                    if status == "error" or "error" in cleaned_output.lower()
                    else ""
                )
                print(
                    f"{color}{cleaned_output}{Colors.RESET}"
                    if color
                    else cleaned_output
                )
                if not cleaned_output.endswith("\n"):
                    print()

    def _display_error_result(self, result_content: List[Dict]) -> None:
        for content_block in result_content:
            if isinstance(content_block, dict) and "text" in content_block:
                error_text = content_block.get("text", "").strip()
                if error_text and error_text != "Error:":
                    print(f"{Colors.RED}Error: {error_text}{Colors.RESET}")
                    if not error_text.endswith("\n"):
                        print()
                    break

    def _display_generic_result(
        self, tool_name: str, result_content: List[Dict]
    ) -> None:
        for content_block in result_content:
            if isinstance(content_block, dict) and "text" in content_block:
                output_text = content_block.get("text", "").strip()
                if output_text:
                    if tool_name == "swarm":
                        print(f"{Colors.CYAN}[Swarm Output]{Colors.RESET}")
                        print(output_text)
                    else:
                        max_lines = 50
                        lines = output_text.split("\n")
                        if len(lines) > max_lines:
                            print("\n".join(lines[:max_lines]))
                            print(
                                f"{Colors.DIM}... ({len(lines) - max_lines} more lines){Colors.RESET}"
                            )
                        else:
                            print(output_text)
                    if not output_text.endswith("\n"):
                        print()
                break

    def _track_tool_effectiveness(self, tool_id: str, tool_result: Dict) -> None:
        """Track tool effectiveness for analysis."""
        tool_use = self.tool_use_map.get(tool_id, {})
        tool_name = tool_use.get("name", "unknown")
        status = tool_result.get("status", "unknown")

        if tool_name not in self.tool_effectiveness:
            self.tool_effectiveness[tool_name] = {"success": 0, "error": 0}

        if status == "success":
            self.tool_effectiveness[tool_name]["success"] += 1
        else:
            self.tool_effectiveness[tool_name]["error"] += 1

    def has_reached_limit(self) -> bool:
        """Check if step limit reached."""
        return self.steps >= self.max_steps

    def should_stop(self) -> bool:
        """Check if agent should stop (step limit or stop tool used)."""
        return self.has_reached_limit() or self.stop_tool_used

    def get_remaining_steps(self) -> int:
        """Get remaining steps for budget management."""
        return max(0, self.max_steps - self.steps)

    def get_budget_urgency_level(self) -> str:
        """Get current budget urgency level for decision making."""
        remaining = self.get_remaining_steps()
        if remaining > 20:
            return "ABUNDANT"
        elif remaining > 10:
            return "CONSTRAINED"
        elif remaining > 5:
            return "CRITICAL"
        return "EMERGENCY"

    def get_summary(self) -> Dict[str, any]:
        """Generate operation summary."""
        return {
            "total_steps": self.steps,
            "tools_created": len(self.created_tools),
            "evidence_collected": self.memory_operations,
            "capability_expansion": self.created_tools,
            "memory_operations": self.memory_operations,
            "operation_id": self.operation_id,
        }

    def get_evidence_summary(self) -> List:
        """Get evidence summary from mem0_memory tool."""
        return []

    def generate_final_report(self, agent: Agent, target: str, objective: str, session_output_dir: Path) -> None:
        """Generates a comprehensive final assessment report using LLM analysis."""
        if self.report_generated:
            return
        self.report_generated = True

        all_evidence = self._retrieve_evidence()
        findings = all_evidence.get("findings", [])
        plans = all_evidence.get("plans", [])

        if not findings:
            self._display_no_evidence_message()
            report_content = self._generate_no_evidence_report(target, objective, plans)
        else:
            try:
                report_content = self._generate_llm_report(
                    agent, target, objective, findings, plans
                )
            except Exception as e:
                console.print(
                    f"[bold red]Error generating final report: {e}[/bold red]"
                )
                self._display_fallback_evidence(findings)
                report_content = self._generate_fallback_report(
                    target, objective, findings
                )

        self._save_report_to_file(report_content, target, objective, session_output_dir)

    def _retrieve_evidence(self) -> Dict[str, List[Dict]]:
        """Retrieves all collected evidence (findings and plans) from the memory system."""
        all_evidence = {"findings": [], "plans": []}
        memory_client = get_memory_client()
        if not memory_client:
            return all_evidence

        agent_user_id = "vulcan_agent"
        try:
            logger.info(
                "Retrieving all memories for user_id: %s for final report",
                agent_user_id,
            )
            raw_memory_output = memory_client.get_all(user_id=agent_user_id)

            if isinstance(raw_memory_output, dict) and "results" in raw_memory_output:
                memory_list = raw_memory_output["results"]
            elif isinstance(raw_memory_output, list):
                memory_list = raw_memory_output
            else:
                logger.warning(
                    f"Unexpected memory format received: {type(raw_memory_output)}"
                )
                memory_list = []

            for mem in memory_list:
                if not isinstance(mem, dict):
                    logger.warning(f"Skipping non-dictionary memory item: {mem}")
                    continue

                metadata = mem.get("metadata", {})
                category = metadata.get("category")

                memory_to_store = {
                    "content": mem.get("memory", "N/A"),
                    "metadata": metadata,
                }

                if category == "finding":
                    all_evidence["findings"].append(memory_to_store)
                elif category == "plan":
                    all_evidence["plans"].append(memory_to_store)

            logger.info(
                f"Retrieved {len(all_evidence['findings'])} findings and {len(all_evidence['plans'])} plans."
            )
        except Exception as e:
            logger.error(
                "Error retrieving evidence from mem0_memory: %s", str(e), exc_info=True
            )

        return all_evidence

    def _display_no_evidence_message(self) -> None:
        """Display message when no evidence is available."""
        print(f"{Colors.YELLOW}No evidence collected during operation{Colors.RESET}")
        print(
            f"{Colors.DIM}Steps completed: {self.steps}/{self.max_steps}{Colors.RESET}"
        )
        print(f"{Colors.DIM}Memory operations: {self.memory_operations}{Colors.RESET}")

    def _generate_llm_report(
        self,
        agent: Agent,
        target: str,
        objective: str,
        findings: List[Dict],
        plans: List[Dict],
    ) -> str:
        """Generate assessment report using LLM analysis."""
        final_plan_str = "No final strategic plan was recorded in memory."
        if plans:
            try:
                versioned_plans = []
                for p in plans:
                    try:
                        plan_content = json.loads(p["content"])
                        if "version" in plan_content:
                            versioned_plans.append(plan_content)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if versioned_plans:
                    sorted_plans = sorted(
                        versioned_plans, key=lambda p: p.get("version", 0), reverse=True
                    )
                    final_plan_str = json.dumps(sorted_plans[0], indent=2)
            except Exception as e:
                logger.error(f"Could not parse or sort plans for report: {e}")
                final_plan_str = "Error parsing the final plan from memory."

        findings_text = [f"{i+1}. {item['content']}" for i, item in enumerate(findings)]
        findings_str = "\n".join(findings_text)

        report_prompt = f"""
As an expert cybersecurity analyst, your task is to synthesize the provided operational data into a professional penetration testing report.

**MISSION CONTEXT:**
- **Target:** {target}
- **Initial Objective:** {objective}

**SUMMARY OF CRITICAL FINDINGS:**
The following discoveries were made during the operation:
{findings_str}

**FINAL STRATEGIC PLAN:**
The final version of the strategic plan that led to these findings was as follows. This reveals the agent's thought process and attack path.
```json
{final_plan_str}
```

**YOUR TASK:**
Based on ALL the information above (the findings AND the final plan), write a comprehensive and professional penetration testing report. The report MUST be structured with the following sections:
1.  **Executive Summary:** A high-level overview for management, summarizing the key risks and business impact.
2.  **Attack Narrative:** Tell the story of the penetration test from start to finish. Describe the strategic decisions made (referencing the plan), the tools used, the discoveries at each step, and how one finding led to the next.
3.  **Vulnerability Details:** For each critical finding, provide a detailed technical breakdown including the vulnerability type (e.g., LFI, RCE), location, and evidence.
4.  **Impact and Risk Assessment:** Explain the potential business and technical impact if these vulnerabilities were exploited by a real attacker.
5.  **Recommendations:** Provide clear, actionable steps for remediation, categorized into immediate, short-term, and long-term actions.
"""
        console.print(
            "[cyan]Analyzing all evidence and generating final report...[/cyan]"
        )

        if not agent or not callable(agent):
            raise ValueError("Agent instance is not available for report generation")

        try:
            report_agent = Agent(
                model=agent.model,
                tools=[],
                system_prompt="You are a professional cybersecurity report writer. Your only task is to generate a report based on the provided data, strictly following the requested section format.",
            )
            raw_report = report_agent(report_prompt)
            return str(raw_report)
        except Exception as e:
            logger.error(f"The report generation agent failed: {e}")
            raise

    def _clean_duplicate_content(self, report_content: str) -> str:
        """Remove duplicate sections from LLM-generated content."""
        report_lines = report_content.split("\n")
        clean_lines = []
        seen_section_markers = set()

        for line in report_lines:
            line_strip = line.strip()
            if (
                line_strip.startswith("# Penetration Testing Report")
                or line_strip.startswith("**Target:")
                or (line_strip.startswith("# ") and "Report" in line_strip)
            ):
                if line_strip in seen_section_markers:
                    break
                seen_section_markers.add(line_strip)
            elif line_strip.startswith("## 1. Executive Summary") and any(
                "## 1. Executive Summary" in existing for existing in clean_lines
            ):
                break
            clean_lines.append(line)

        return "\n".join(clean_lines)

    def _save_report_to_file(
        self, report_content: str, target: str, objective: str, session_output_dir: Path
    ) -> None:
        """Save report to file in evidence directory."""
        try:
            evidence_dir = session_output_dir / "evidence"
            evidence_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"final_report_{timestamp}.md"
            report_path = evidence_dir / report_filename

            with open(report_path, "w", encoding="utf-8") as f:
                f.write("# Cybersecurity Assessment Report\n\n")
                f.write(f"**Operation ID:** {self.operation_id}\n")
                f.write(f"**Target:** {target}\n")
                f.write(f"**Objective:** {objective}\n")
                f.write(
                    f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )
                f.write("---\n\n")
                f.write(report_content)

            print(f"\n{Colors.GREEN}Report saved to: {report_path}{Colors.RESET}")
        except Exception as e:
            print(
                f"{Colors.YELLOW}Warning: Could not save report to file: {str(e)}{Colors.RESET}"
            )

    def _generate_no_evidence_report(
        self, target: str, objective: str, plans: List[Dict]
    ) -> str:
        """Generate a report when no evidence was collected."""
        summary = self.get_summary()
        plan_summary = (
            "No strategic plan was recorded."
            if not plans
            else f"{len(plans)} plan versions were created during the operation."
        )
        return f"""## Assessment Summary

Status: No evidence (findings) collected during assessment.
Operation Details
Steps completed: {summary["total_steps"]}/{self.max_steps}
Memory operations: {summary["memory_operations"]}
Planning Activity: {plan_summary}
Possible Reasons
The target may not have been reachable or vulnerable.
The operation may have been interrupted before significant findings were made.
Review the execution log for tool errors or other issues.
"""

    def _generate_fallback_report(
        self, target: str, objective: str, evidence: List[Dict]
    ) -> str:
        """Generate a fallback report when LLM generation fails."""
        summary = self.get_summary()
        evidence_summary = ""
        categories = {}
        for item in evidence:
            cat = item.get("metadata", {}).get("category", "unknown")
            categories.setdefault(cat, []).append(item.get("content", ""))

        for category, items in categories.items():
            evidence_summary += f"\n### {category.title()} Findings\n"
            for i, item in enumerate(items[:5], 1):
                evidence_summary += (
                    f"{i}. {item[:200]}{'...' if len(item) > 200 else ''}\n"
                )
            if len(items) > 5:
                evidence_summary += f"... and {len(items) - 5} more items\n"

        return f"""## Assessment Summary

**Status:** Evidence collected but LLM report generation failed

### Operation Details
- Steps completed: {summary["total_steps"]}/{self.max_steps}
- Tools created: {summary["tools_created"]}
- Evidence items: {len(evidence)}
- Memory operations: {summary["memory_operations"]}

### Evidence Collected
{evidence_summary}

### Note
This is a fallback report generated when AI analysis was unavailable. 
Review the evidence items above for detailed findings.
"""

    def _display_fallback_evidence(self, evidence: List[Dict]) -> None:
        """Display evidence summary as fallback when LLM generation fails."""
        print(f"\n{Colors.YELLOW}Displaying collected evidence instead:{Colors.RESET}")
        for i, item in enumerate(evidence, 1):
            category = item["metadata"].get("category", "unknown")
            content_preview = item["content"][:FALLBACK_EVIDENCE_PREVIEW_LENGTH]
            print(f"\n{i}. {Colors.GREEN}[{category}]{Colors.RESET}")
            print(
                f"   {content_preview}{'...' if len(item['content']) > FALLBACK_EVIDENCE_PREVIEW_LENGTH else ''}"
            )
            if len(item["content"]) > FALLBACK_EVIDENCE_PREVIEW_LENGTH:
                print(f"   {Colors.DIM}(truncated){Colors.RESET}")
