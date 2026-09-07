import unittest

from chat.language import detect_response_language


class ResponseLanguageDetectionTest(unittest.TestCase):
    def test_korean_question_uses_korean(self):
        self.assertEqual(detect_response_language("처리 방법을 알려줘"), "ko")

    def test_korean_question_with_long_english_business_term_stays_korean(self):
        self.assertEqual(detect_response_language("SWIFT Code 오류 처리 방법"), "ko")

    def test_english_question_uses_english(self):
        self.assertEqual(detect_response_language("How do I process screen 9043?"), "en")

    def test_current_question_can_switch_language(self):
        history = [{"role": "user", "text": "처리 방법을 알려줘"}]
        self.assertEqual(detect_response_language("Please explain it again", history), "en")

    def test_language_neutral_followup_uses_previous_user_language(self):
        history = [{"role": "user", "text": "Which screen is this?"}]
        self.assertEqual(detect_response_language("9043", history), "en")


if __name__ == "__main__":
    unittest.main()
