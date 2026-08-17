import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.persistence.entities import Base
from app.persistence.repositories import ChatMessageRepository


class ChatHistoryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.session = Session(bind=self.engine)
        self.repository = ChatMessageRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()

    def test_persists_and_reads_recent_messages(self) -> None:
        self.repository.add_message(
            user_id=1,
            username="admin",
            session_id="session-1",
            role="user",
            content="Hello there",
        )
        self.repository.add_message(
            user_id=1,
            username="admin",
            session_id="session-1",
            role="assistant",
            content="Hello back",
            prompt_tokens=10,
            completion_tokens=8,
            total_tokens=18,
        )
        self.repository.add_message(
            user_id=1,
            username="admin",
            session_id="session-2",
            role="assistant",
            content="Should not appear",
        )

        messages = self.repository.list_recent_messages(user_id=1, session_id="session-1", limit=5)

        self.assertEqual([(message.role, message.content) for message in messages], [
            ("user", "Hello there"),
            ("assistant", "Hello back"),
        ])
        self.assertEqual(messages[1].prompt_tokens, 10)
        self.assertEqual(messages[1].completion_tokens, 8)
        self.assertEqual(messages[1].total_tokens, 18)


if __name__ == "__main__":
    unittest.main()
