import unittest

from app.core.message import ChatMessage, MessagePart


class ChatVNextContractTests(unittest.TestCase):
    def test_typed_message_contract_is_persistence_neutral(self):
        message = ChatMessage(
            message_id="m1", session_id="s1", parent_id=None, role="assistant",
            created_at="2026-08-12T00:00:00+00:00", mode="canonical",
            parts=(MessagePart("text", {"text": "hello"}),),
            model={"id": "owner/model", "revision": "abc"},
        ).to_dict()
        self.assertEqual(message["parts"], [{"type": "text", "text": "hello"}])
        self.assertNotIn("storage_path", message)


if __name__ == "__main__":
    unittest.main()
