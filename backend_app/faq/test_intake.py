import unittest
from unittest.mock import patch

from faq.intake import LocalizedChatResponse, _clean_display_options, localize_chat_response


class ChatOptionCleanupTest(unittest.TestCase):
    def test_placeholder_options_are_removed(self):
        self.assertEqual(
            _clean_display_options(["", "(None)", "(없음)", "null", "실제 선택지"]),
            ["실제 선택지"],
        )

    @patch("faq.intake.localization_llm")
    def test_localizer_cannot_create_option_when_source_is_empty(self, mock_localizer):
        mock_localizer.invoke.return_value = LocalizedChatResponse(
            text="질문입니다.", options=["(None)"]
        )

        result = localize_chat_response("질문입니다.", [], "ko")

        self.assertEqual(result.options, [])


if __name__ == "__main__":
    unittest.main()
