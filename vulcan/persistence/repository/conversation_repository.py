import uuid

from vulcan.persistence.models.conversation_model import Conversation
from vulcan.persistence.db_session import with_session


@with_session
def add_conversation_to_db(session, chat_type: str, conversation_id=None):

    if not conversation_id:
        conversation_id = uuid.uuid4().hex
        conversation = Conversation(id=conversation_id, chat_type=chat_type)
        session.add(conversation)

    return conversation_id

