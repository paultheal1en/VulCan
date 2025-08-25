import re
from typing import Optional
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

from vulcan.agent_core.tools.shell_tool import safe_shell 
from vulcan.actions.prompts.apg_prompt import APGPrompt 
from vulcan.llm.chat_llm import _chat 
from vulcan.utils.log_common import build_logger

logger = build_logger("APG")

class APGResult(BaseModel):
    """Kết quả trả về từ module APG."""
    success: bool
    final_result: Optional[ExecuteResult] = None
    refined_command: Optional[str] = None
    attempts_history: list = Field(default_factory=list)

class AdaptivePayloadGenerator(BaseModel):
    """Module tinh chỉnh payload thất bại một cách lặp đi lặp lại."""
    initial_command: str
    initial_result: str
    action_type: str
    max_refinements: int = 5
    console: Console = Field(default_factory=Console)

    class Config:
        arbitrary_types_allowed = True

    def run(self) -> APGResult:
        """
        Thực thi vòng lặp tinh chỉnh payload.
        """
        self.console.print("[bold cyan]Entering Adaptive Payload Generation Module...[/bold cyan]")

        current_command = self.initial_command
        last_result = self.initial_result
        history = []
        
        for i in range(self.max_refinements):
            self.console.print(f"--- APG Iteration {i + 1}/{self.max_refinements} ---", style="yellow")
            
            # Xây dựng chuỗi lịch sử cho prompt, làm cho nó dễ đọc hơn
            history_str = "\n".join(
                [f"- Attempt: `{att['command']}`\n  Result: `{att['result'][:150].replace('`', '')}...`" for att in history]
            )
            if not history_str:
                history_str = "No previous attempts in this cycle."

            # 1. Yêu cầu LLM tạo ra payload mới, CÓ cung cấp lịch sử
            prompt = APGPrompt.refine_payload_prompt.format(
                failed_command=current_command,
                execution_result=last_result,
                attempts_history=history_str
            )
            llm_response, _ = _chat(query=prompt, summary=False)
            
            match = re.search(r'<execute>(.*?)</execute>', llm_response, re.DOTALL)
            if not match:
                self.console.print("[red]APG Error: LLM did not return a valid command.[/red]")
                # Trả về kết quả thất bại cuối cùng thay vì None
                final_execution_result = ExecuteResult(context={'action': self.action_type, 'code': [current_command]}, response=last_result)
                return APGResult(success=False, final_result=final_execution_result, attempts_history=history)

            refined_command = match.group(1).strip()

            # --- THÊM KIỂM TRA LẶP LẠI ---
            if refined_command == current_command or any(att['command'] == refined_command for att in history):
                self.console.print("[bold red]APG Warning: LLM suggested a repeated command. Ending refinement cycle.[/bold red]")
                break # Thoát khỏi vòng lặp nếu LLM hết ý tưởng

            self.console.print(f"LLM suggested refinement: [green]{refined_command}[/green]")

            # 2. Thực thi payload mới
            executor = ExecuteTask(action=self.action_type, instruction=f"<execute>{refined_command}</execute>", code=[refined_command])
            execution_result = executor.run()
            
            command_executed_in_apg = " ".join(execution_result.context.get('code', []))
            output_files_matches = re.findall(r'(-o[A-Z]?|--output|-D|--dump-header)\s+([\'"]?[\w\.\-\/]+[\'"]?)|>\s+([\'"]?[\w\.\-\/]+[\'"]?)', command_executed_in_apg)
        
            if output_files_matches:
                files_to_read = [path.strip('\'"') for match in output_files_matches for path in match if path and not path.startswith('-')]
                if files_to_read:
                    self.console.print(f"[cyan]APG: Detected output redirection. Reading files: {files_to_read}[/cyan]")
                    shell = ShellManager.get_instance().get_shell()
                    full_output = []
                    for filepath in files_to_read:
                        read_command = f"cat {filepath}"
                        file_content = shell.execute_cmd(read_command)
                        full_output.append(f"--- Content of {filepath} ---\n{file_content}")
                    
                    if execution_result.response.strip():
                        execution_result.response = "\n".join(full_output) + "\n\n--- Standard Output ---\n" + execution_result.response
                    else:
                        execution_result.response = "\n".join(full_output)
            self.console.print(f"Execution result: {execution_result.response}...", style="dim")

            # 3. Kiểm tra xem lần tinh chỉnh này có thành công không
            success_prompt = APGPrompt.check_refinement_success.format(
                previous_result=last_result,
                current_result=execution_result.response
            )
            success_check, _ = _chat(query=success_prompt, summary=False)

            if "yes" in success_check.lower():
                self.console.print("[bold green]APG Success: Refinement led to progress or success![/bold green]")
                return APGResult(success=True, final_result=execution_result, refined_command=refined_command, attempts_history=history)

            # Nếu không thành công, cập nhật trạng thái cho vòng lặp tiếp theo
            current_command = refined_command
            last_result = execution_result.response
            history.append({"command": current_command, "result": last_result})
            self.console.print("[yellow]Refinement did not yield progress. Retrying...[/yellow]")

        self.console.print("[bold red]APG Finished: Max refinement attempts reached without success.[/bold red]")
        # Tạo một bản tóm tắt các nỗ lực thất bại của APG
        failure_summary = "Adaptive Payload Generator failed after multiple attempts. Analysis of attempts:\n"
        for attempt in history:
            command = attempt['command']
            # Cắt ngắn kết quả để không làm prompt quá dài
            result_snippet = attempt['result'].replace('\n', ' ').strip()[:150]
            failure_summary += f"- Command: `{command}`\n  - Result: `{result_snippet}...`\n"
        
        # Ghép tóm tắt vào kết quả cuối cùng để Planner biết
        final_observation_with_summary = f"{failure_summary}\nFinal Observation from the last attempt:\n{last_result}"

        final_execution_result = ExecuteResult(
            context={'action': self.action_type, 'code': [current_command]}, 
            response=final_observation_with_summary # Sử dụng response đã được bổ sung thông tin
        )
        return APGResult(success=False, final_result=final_execution_result, attempts_history=history)