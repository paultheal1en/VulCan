import dataclasses

@dataclasses.dataclass
class ClassifierPrompt:
    classify_failure: str = """You are a senior penetration tester analyzing the result of a failed command. Your task is to classify the failure into one of two categories: "Environmental Error" or "Tactical Failure".

    **1. Environmental Error:**
    This category is for problems with the tool or the environment itself. The command could not execute correctly.
    - Examples: `command not found`, `Permission denied`, `No such file or directory`, `Connection refused`, network timeouts, Python tracebacks, invalid command syntax/flags.

    **2. Tactical Failure:**
    This category is for when the command executed successfully, but the intended goal was not achieved due to the target's defenses or application logic. The *tactic* failed, not the tool.
    - Examples: `403 Forbidden`, `Blocked by WAF`, `Invalid credentials`, `Access Denied`, `Page not found` (when attempting LFI/directory traversal), a login page is returned instead of the expected content.

    **Analysis Task:**
    - **Instruction:** {instruction}
    - **Command Executed:** `{command}`
    - **Execution Result:**
    ```
    {result}
    ```

    **Your Response:**
    Based on your analysis, respond with ONLY ONE of the following keywords:
    - `ENVIRONMENTAL`
    - `TACTICAL`
    """