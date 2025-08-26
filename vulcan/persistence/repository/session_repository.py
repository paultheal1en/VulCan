import uuid
import time
from typing import List

from ..models.session_model import Session, SessionModel  
from ..db_session import with_session  


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
        init_description=session_data.init_description,
    )

    session.add(new_session_model)
    session.commit()  
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
            init_description=session_data.init_description or "",
        )

        existing_session = session.query(SessionModel).filter_by(id=session_data.id).first()

        if existing_session:
            existing_session.name = session_model.name
            existing_session.init_description = session_model.init_description

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
