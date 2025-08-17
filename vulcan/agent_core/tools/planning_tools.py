from typing import List, Dict, Optional
from strands import tool
import uuid

from vulcan.persistence.models.plan_model import Plan
from vulcan.persistence.models.task_model import Task
from vulcan.persistence.repository.plan_repository import add_plan_to_db
from vulcan.persistence.repository.task_repository import add_tasks_to_db

@tool
def update_plan_db(
    session_id: str,
    goal: str,
    plan_steps: List[Dict],
    current_plan_id: Optional[str] = None,
) -> str:
    """
    Creates a new plan or updates an existing one in the database.
    Use this to record your strategic thinking and next actions.

    Args:
        session_id: The ID of the current session.
        goal: The overall goal of this plan phase.
        plan_steps: A list of dictionaries, where each dictionary represents a task.
                    Example: [{"action": "shell", "instruction": "Run nmap scan", "dependencies": []}]
        current_plan_id: The ID of the plan to update. If None, a new plan will be created.
    """
    try:
        if current_plan_id:
            # TODO: Implement plan update logic in the future
            return f"Plan update functionality for plan {current_plan_id} is not yet implemented."
        else:
            # Tạo một plan mới
            # GIẢI THÍCH: Chúng ta sẽ cần session_id để liên kết Plan với Session,
            # nhưng model Plan hiện tại chưa có trường này. Sẽ cập nhật sau.
            plan = Plan(goal=goal) 
            plan = add_plan_to_db(plan) # Lưu plan để có ID

        # Tạo các đối tượng Task
        tasks = []
        for i, step in enumerate(plan_steps):
            task = Task(
                id=uuid.uuid4().hex, # Gán ID cho task
                plan_id=plan.id,
                sequence=i,
                action=step.get("action", "Unknown"),
                instruction=step.get("instruction", ""),
                dependencies=step.get("dependencies", [])
            )
            tasks.append(task)
        
        # Thêm các task vào DB
        add_tasks_to_db(tasks)

        # Cập nhật planner_id hiện tại của session
        from vulcan.persistence.session_manager import update_current_planner_id
        update_current_planner_id(session_id, plan.id)

        return f"Successfully created a new plan with ID {plan.id} and {len(tasks)} tasks."
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error updating plan in database: {e}"