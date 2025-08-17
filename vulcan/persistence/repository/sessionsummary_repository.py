import uuid
from vulcan.persistence.models.session_summary import SessionSummary
from vulcan.persistence.db_session import with_session
from typing import List

@with_session
def get_session_summaries_by_session_id(session, session_id: str) -> List[SessionSummary]:
    """
    Lấy tất cả các bản summary theo session_id.
    """
    summaries = session.query(SessionSummary).filter_by(session_id=session_id).all()
    combined_summary = "\n\n".join([summary.summary for summary in summaries])
    return combined_summary

@with_session
def save_session_summary(session, session_id: str, summary: str):
    session_summary = SessionSummary(
        id=uuid.uuid4().hex,
        session_id=session_id,
        summary=summary
    )
    session.add(session_summary)
    session.commit()
    