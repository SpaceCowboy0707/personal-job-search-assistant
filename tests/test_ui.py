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
        # Tests must not depend on a developer's real local secret file.
        key = patch('job_assistant.api_model.api_key', side_effect=lambda root: os.environ.get('OPENAI_API_KEY', ''))
        key.start()
        self.addCleanup(key.stop)
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

    def test_language_toggle_preserves_page_and_job_without_api_calls(self):
        from streamlit.testing.v1 import AppTest
        from job_assistant import workspace as ws
        from job_assistant.i18n import catalog
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / 'test.db'
            jid = ws.import_job(root, db, root/'output', SAMPLE_RESUME, {'company':'Example', 'job_title':'Analyst', 'source_url':'https://www.builtinnyc.com/job/analyst/123', 'jd':'SQL analysis', 'location':'NYC'})
            with patch.dict(os.environ, {'JOB_ASSISTANT_DB':str(db)}), patch.object(ws, 'structured_call') as api:
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
                app.sidebar.radio[0].set_value('Job inbox').run()
                app.button(key='toggle_language').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.title[0].value, catalog()['Job inbox'])
                self.assertEqual(app.session_state['ui_Workspace'], 'Job inbox')
                self.assertEqual(app.session_state['inbox_selection'], jid)
                self.assertEqual(app.text_area(key=f'full_jd_text_{jid}').value, 'SQL analysis')
                app.button(key='toggle_language').click().run()
                self.assertEqual(app.title[0].value, 'Job inbox')
                self.assertEqual(app.session_state['inbox_selection'], jid)
                api.assert_not_called()

    def test_job_cards_select_and_filter_without_api(self):
        from streamlit.testing.v1 import AppTest
        from job_assistant import workspace as ws
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / 'test.db'
            ids = []
            for company in ('First', 'Second'):
                ids.append(ws.import_job(root, db, root/'output', SAMPLE_RESUME, {'company': company, 'job_title':'Analyst', 'source_url':'', 'jd':company + ' SQL analysis', 'location':'NYC'}))
            with patch.dict(os.environ, {'JOB_ASSISTANT_DB':str(db)}), patch.object(ws, 'structured_call') as api:
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
                app.sidebar.radio[0].set_value('Job inbox').run()
                self.assertFalse(any(s.label == 'Open job' for s in app.selectbox))
                app.button(key=f'open_job_{ids[0]}').click().run()
                self.assertEqual(app.session_state['inbox_selection'], ids[0])
                self.assertEqual(app.text_area(key=f'full_jd_text_{ids[0]}').value, 'First SQL analysis')
                app.text_input(key='inbox_query').set_value('Second').run()
                self.assertEqual(app.session_state['inbox_selection'], ids[1])
                self.assertFalse(any(b.key == f'open_job_{ids[0]}' for b in app.button))
                app.text_input(key='inbox_query').set_value('No such company').run()
                self.assertTrue(app.info)
                self.assertFalse(app.exception)
                api.assert_not_called()

    def test_inbox_generation_rerun_approval_and_stale_version(self):
        from streamlit.testing.v1 import AppTest
        from job_assistant import workspace as ws
        from job_assistant.resume import read_resume
        from job_assistant.tracker import connect
        fact = next(f for f in read_resume(SAMPLE_RESUME)['facts'] if f['section'] in ('experience', 'professional experience') and ':' in f['text'])
        generated = {'data': {'bullets': [{'source_id': fact['id'], 'text': fact['text'], 'why': 'Relevant original evidence'}]}, 'run_id': 'g', 'estimated_cost_usd': .001}
        checked = {'data': {'checks': [{'index': 0, 'supported': True, 'reason': 'Original wording'}]}, 'run_id': 'c', 'estimated_cost_usd': .001}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / 'test.db'
            jid = ws.import_job(root, db, root/'output', SAMPLE_RESUME, {'company':'Example', 'job_title':'Analyst', 'source_url':'https://www.builtinnyc.com/job/analyst/123', 'jd':'SQL analysis', 'location':'NYC'})
            with patch.dict(os.environ, {'JOB_ASSISTANT_DB':str(db), 'JOB_ASSISTANT_OUTPUT':str(root/'output')}), patch.object(ws, 'structured_call', side_effect=[generated, checked]) as call:
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
                app.sidebar.radio[0].set_value('Job inbox').run()
                self.assertFalse(app.exception)
                next(b for b in app.button if b.label == 'Generate tailored bullets').click().run()
                self.assertFalse(app.exception)
                app.run()
                self.assertEqual(call.call_count, 2)
                next(b for b in app.button if b.label == 'Approve this bullet version').click().run()
                with connect(db) as conn:
                    self.assertEqual(conn.execute('SELECT approved FROM bullet_versions').fetchone()[0], 1)
                ws.save_full_jd(db, jid, 'SQL and additional requirements')
                app.run()
                self.assertFalse(app.exception)
                self.assertFalse(any(b.label == 'Approve this bullet version' for b in app.button))
