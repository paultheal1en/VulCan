import uuid
import time
from typing import List

from ..models.session_model import Session, SessionModel  # ✅ Import chuẩn từ models
from ..db_session import with_session  # ✅ Import chuẩn từ db_session


@with_session
def add_session_to_db(session, session_data: Session) -> Session:
    """
    Thêm một session mới vào database và trả về đối tượng session đã hoàn chỉnh.
    """
    # Gán ID nếu chưa có
    if not session_data.id:
        session_data.id = uuid.uuid4().hex

    # Gán tên mặc định nếu chưa có
    if not session_data.name:
        session_data.name = f"Session_{int(time.time())}"

    # Tạo đối tượng SQLAlchemy model từ đối tượng Pydantic model
    new_session_model = SessionModel(
        id=session_data.id,
        name=session_data.name,
        current_role_name=session_data.current_role_name,
        init_description=session_data.init_description,
        current_planner_id=session_data.current_planner_id,
        history_planner_ids=",".join(session_data.history_planner_ids) if session_data.history_planner_ids else ""
    )

    session.add(new_session_model)
    session.commit()  # ✅ Commit để đảm bảo lưu DB

    return session_data


@with_session
def fetch_all_sessions(session) -> List[Session]:
    """
    Lấy tất cả các session từ database và trả về dạng Pydantic model.
    """
    result = session.query(SessionModel).all()
    result = [Session.model_validate(r) for r in result]
    return result


@with_session
def update_session_in_db(session, session_data: Session) -> Session:
    """
    Update an existing session in the database.
    
    Args:
        session: SQLAlchemy session (injected by decorator)
        session_data: Session object to update
    """
    try:
        session_model = SessionModel(
            id=session_data.id,
            name=session_data.name or "",
            current_role_name=session_data.current_role_name or "",
            init_description=session_data.init_description or "",
            current_planner_id=session_data.current_planner_id or "",
            history_planner_ids=",".join(session_data.history_planner_ids) if session_data.history_planner_ids else ""
        )

        existing_session = session.query(SessionModel).filter_by(id=session_data.id).first()

        if existing_session:
            existing_session.name = session_model.name
            existing_session.current_role_name = session_model.current_role_name
            existing_session.init_description = session_model.init_description
            existing_session.current_planner_id = session_model.current_planner_id
            existing_session.history_planner_ids = session_model.history_planner_ids

            session.commit()
            return session_data
        else:
            session.add(session_model)
            session.commit()
            return session_data

    except Exception as e:
        session.rollback()
        print(f"Error updating session: {e}")
        raise e
