import unittest
from unittest.mock import patch

from faq.intake import ConversationContext
from chat import workflow


def _context() -> ConversationContext:
    return ConversationContext(
        summary="요약",
        active_business_question="질문",
        confirmed_facts=[],
        pending_clarification="",
        is_aither_business_context=True,
        current_message_is_followup=False,
    )


class ChatWorkflowTest(unittest.TestCase):
    def _run(self, **overrides):
        params = {
            "message": "질문",
            "room_id": 1,
            "username": "tester",
            "history": [],
            "language": "ko",
        }
        params.update(overrides)
        return workflow.run_chat_workflow(**params)

    @patch.object(workflow.faq_intake, "handle_pre_search_action")
    @patch.object(workflow.faq_intake, "summarize_conversation_context")
    def test_pre_search_can_complete_early(self, summarize, pre_search):
        summarize.return_value = _context()
        pre_search.return_value = {
            "type": "answer",
            "text": "완료",
            "options": [],
            "sources": [],
        }

        state = self._run()

        self.assertEqual(state.result["text"], "완료")
        self.assertEqual(
            [step["input"]["action"] for step in state.transitions],
            ["summarize_context", "handle_pre_search"],
        )
        self.assertEqual(state.transitions[-1]["output"]["next_action"], "complete")

    @patch.object(workflow.faq_intake, "handle_unresolved_question")
    @patch.object(workflow.knowledge_router, "answer_from_latest_knowledge")
    @patch.object(workflow.screen_owners, "answer_screen_owner_request")
    @patch.object(workflow.faq_intake, "redirect_non_business_chat_if_applicable")
    @patch.object(workflow.faq_intake, "handle_pre_search_action")
    @patch.object(workflow.faq_intake, "summarize_conversation_context")
    def test_unresolved_question_runs_full_route(
        self,
        summarize,
        pre_search,
        route_business,
        owner_change,
        knowledge,
        unresolved,
    ):
        summarize.return_value = _context()
        pre_search.return_value = None
        route_business.return_value = None
        owner_change.return_value = None
        knowledge.return_value = {
            "type": "answer",
            "answerable": False,
            "text": "없음",
            "options": [],
            "sources": [],
        }
        unresolved.return_value = {
            "type": "clarify",
            "text": "추가 질문",
            "options": [],
            "sources": [],
        }

        state = self._run()

        self.assertEqual(state.result["text"], "추가 질문")
        self.assertEqual(
            [step["input"]["action"] for step in state.transitions],
            [
                "summarize_context",
                "handle_pre_search",
                "route_business",
                "handle_owner_change",
                "search_knowledge",
                "handle_unresolved",
            ],
        )

    def test_runner_stops_an_infinite_loop(self):
        def repeat_same_action(_state):
            return workflow.ChatAction.SUMMARIZE_CONTEXT

        handlers = {
            **workflow.ACTION_HANDLERS,
            workflow.ChatAction.SUMMARIZE_CONTEXT: repeat_same_action,
        }
        with patch.object(workflow, "ACTION_HANDLERS", handlers):
            with self.assertRaisesRegex(RuntimeError, "최대 실행 횟수"):
                self._run(max_steps=2)


if __name__ == "__main__":
    unittest.main()
