import uuid

from vulcan.persistence.models.plan_model import Plan, PlanModel
from vulcan.persistence.db_session import with_session


@with_session
def get_planner_by_id(session, planner_id: str):
    plan_model = session.query(PlanModel).filter(PlanModel.id == planner_id).first()
    if plan_model:
        plan = Plan.model_validate(plan_model)
        return plan
    return None


@with_session
def add_plan_to_db(session, plan: Plan) -> Plan:
    if not plan.id:
        plan.id = uuid.uuid4().hex
    
    new_plan_model = PlanModel(
        id=plan.id,
        goal=plan.goal,
        current_task_sequence=plan.current_task_sequence or 0,
        plan_chat_id=plan.plan_chat_id or "",
        react_chat_id=plan.react_chat_id or ""
    )
    session.add(new_plan_model)
    session.commit()
    return plan

@with_session
def update_plan_in_db(session, plan: Plan):
    existing_plan = session.query(PlanModel).filter(PlanModel.id == plan.id).first()
    if existing_plan:
        existing_plan.goal = plan.goal
        existing_plan.current_task_sequence = plan.current_task_sequence
        existing_plan.plan_chat_id = plan.plan_chat_id
        existing_plan.react_chat_id = plan.react_chat_id
        session.commit()
    else:
        raise ValueError(f"Plan with id {plan.id} not found.")