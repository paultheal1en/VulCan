import uuid
from typing import List

from vulcan.persistence.models.task_model import TaskModel, Task
from vulcan.persistence.db_session import with_session


@with_session
def add_tasks_to_db(session, tasks: List[Task]):
    """Add a new task to a plan"""
    new_tasks = []
    for task in tasks:
        new_task = TaskModel(id=task.id or uuid.uuid4().hex,
                             plan_id=task.plan_id,
                             sequence=task.sequence,
                             action=task.action,
                             instruction=task.instruction,
                             code=task.code,
                             dependencies=task.dependencies,
                             is_finished=task.is_finished,
                             is_success=task.is_success,
                             result=task.result[:8192])
        new_tasks.append(new_task)

    session.add_all(new_tasks)
@with_session
def update_task_status(session, task_id: str, is_finished: bool, is_success: bool, result: str):
    """Updates the status of a specific task by its ID."""
    task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
    if task:
        task.is_finished = is_finished
        task.is_success = is_success
        task.result = result[:8192] if result else ""
        session.commit()