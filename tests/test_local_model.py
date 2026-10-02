import unittest
from job_assistant.local_model import request, validate_advice


class LocalModelTests(unittest.TestCase):
    def test_remote_endpoint_blocked_before_upload(self):
        for url in ('https://example.com', 'http://localhost@example.com', 'http://127.0.0.1/path'):
            with self.assertRaises(ValueError):
                request({'base_url': url}, '/api/chat', {'private': 'resume'})

    def test_fabricated_source_rejected(self):
        with self.assertRaises(ValueError):
            validate_advice({'emphasis': [{'source_id': 'P999', 'reason': 'SQL'}],
                             'possible_gaps': [], 'questions': []}, [{'id': 'P001', 'text': 'SQL'}])

    def test_source_text_from_master_only(self):
        result = validate_advice({'emphasis': [{'source_id': 'P001', 'reason': 'Relevant'}],
                                  'possible_gaps': [], 'questions': []}, [{'id': 'P001', 'text': 'Actual fact'}])
        self.assertEqual(result['emphasis'][0]['source_text'], 'Actual fact')
