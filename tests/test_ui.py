"""UI workflow smoke tests use isolated data, never the personal tracker."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SAMPLE_RESUME = str(Path(__file__).resolve().parents[1] / 'examples/resume.txt')


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Optional Streamlit dependency not installed')
class UITests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'JOB_ASSISTANT_RESUME': SAMPLE_RESUME})
        env.start()
        self.addCleanup(env.stop)
    def test_api_page_missing_key_and_mocked_call(self):
        from streamlit.testing.v1 import AppTest
        from job_assistant.api_model import usage
        response = {'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 100},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text':
                        json.dumps({'emphasis': [], 'possible_gaps': ['Test gap'], 'questions': []})}]}]}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'JOB_ASSISTANT_DB': str(Path(temp) / 'test.db'), 'OPENAI_API_KEY': ''}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
            app.sidebar.radio[0].set_value('Agent settings and trial').run()
            self.assertFalse(app.exception)
            self.assertTrue(next(b for b in app.button if b.label == 'Generate and save API suggestions').disabled)
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), patch('job_assistant.api_model.send', return_value=response) as send:
                app.run()
                next(t for t in app.text_area if t.label == 'Trial job description').set_value('SQL analyst')
                next(b for b in app.button if b.label == 'Generate and save API suggestions').click().run()
                self.assertFalse(app.exception)
                app.run()
                self.assertEqual(send.call_count, 1)
                self.assertEqual(len(usage(Path(temp) / 'test.db')['rows']), 1)

    def test_analyze_rerun_and_update(self):
        from streamlit.testing.v1 import AppTest
        from job_assistant.tracker import connect

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(os.environ, {'JOB_ASSISTANT_DB': str(root / 'test.sqlite3'), 'JOB_ASSISTANT_OUTPUT': str(root / 'output')}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
                self.assertFalse(app.exception)
                app.button(key='load_example').click().run()
                next(b for b in app.button if b.label == 'Analyze and save to tracker').click().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.success)
                result = app.session_state['latest_result']
                self.assertIn('tailored_resume_draft', result)
                app.run()
                with connect(root / 'test.sqlite3') as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0], 1)
                app.sidebar.radio[0].set_value('Job tracker').run()
                self.assertFalse(app.exception)
                next(s for s in app.selectbox if s.label == 'Job status').set_value('REVIEWED')
                next(t for t in app.text_area if t.label == 'Job notes').set_value('UI workflow verified')
                next(b for b in app.button if b.label == 'Save status and notes').click().run()
                self.assertFalse(app.exception)
                with connect(root / 'test.sqlite3') as db:
                    row = db.execute('SELECT * FROM jobs').fetchone()
                    self.assertEqual(row['status'], 'REVIEWED')
                    self.assertEqual(row['notes'], 'UI workflow verified')
                    self.assertEqual(json.loads(row['analysis_json'])['overall_match_score'], result['overall_match_score'])
                app.sidebar.radio[0].set_value('Master resume').run()
                self.assertFalse(app.exception)
                self.assertTrue(app.success)

    def test_empty_input_has_visible_error(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
        next(b for b in app.button if b.label == 'Analyze and save to tracker').click().run()
        self.assertFalse(app.exception)
        self.assertIn('Enter a job description first', app.error[0].value)
