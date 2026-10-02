import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from job_assistant import api_model as api


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'test.db'
        self.resume = {'sha256': 'original', 'facts': [{'id': 'P001', 'text': 'SQL', 'section': 'skills'}]}
        self.limits = {'daily_usd': 1, 'monthly_usd': 20}

    def test_missing_key_no_call_no_charge(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}), patch.object(api, 'send') as send:
            with self.assertRaises(ValueError):
                api.advise(self.root, self.db, self.limits, self.resume, 'SQL role')
            send.assert_not_called()
            self.assertEqual(api.usage(self.db)['day'], 0)

    def test_budget_blocks_second_reservation(self):
        limits = {'daily_usd': .1, 'monthly_usd': 20}
        api.reserve(self.db, limits, 'hash')
        with self.assertRaises(ValueError):
            api.reserve(self.db, limits, 'hash')

    def test_timeout_preserves_reserve_no_retry(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), patch.object(api, 'send', side_effect=TimeoutError) as send:
            with self.assertRaises(TimeoutError):
                api.advise(self.root, self.db, self.limits, self.resume, 'SQL role')
            self.assertEqual(send.call_count, 1)
            self.assertEqual(api.usage(self.db)['day'], .1)
            self.assertEqual(api.usage(self.db)['rows'][0]['status'], 'OUTCOME_UNKNOWN')

    def test_invalid_source_still_accounts_usage(self):
        self.response_case('P999', False)

    def test_success_saved_and_costed(self):
        self.response_case('P001', True)

    def response_case(self, source, valid):
        content = {'emphasis': [{'source_id': source, 'reason': 'SQL'}], 'possible_gaps': [], 'questions': []}
        response = {'status': 'completed', 'usage': {'input_tokens': 6000, 'output_tokens': 2000},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(content)}]}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), patch.object(api, 'send', return_value=response) as send:
            if valid:
                result = api.advise(self.root, self.db, self.limits, self.resume, 'SQL role')
                self.assertEqual(result['emphasis'][0]['source_text'], 'SQL')
            else:
                with self.assertRaises(ValueError):
                    api.advise(self.root, self.db, self.limits, self.resume, 'SQL role')
            self.assertFalse(send.call_args.args[0]['store'])
            self.assertEqual(send.call_count, 1)
        self.assertAlmostEqual(api.usage(self.db)['day'], .0135)
        self.assertEqual(api.usage(self.db)['rows'][0]['status'], 'SUCCEEDED' if valid else 'INVALID_RESPONSE')
