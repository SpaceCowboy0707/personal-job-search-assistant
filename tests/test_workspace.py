import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from job_assistant import workspace as ws
from job_assistant.resume import read_resume
from job_assistant.tracker import connect


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'jobs.db'
        self.resume = self.root / 'resume.txt'
        self.resume.write_text('Candidate\nEXPERIENCE\nExample Employer\nAnalyst\nReporting: Built 4 SQL reports.\n', encoding='utf-8')
        self.limits = {'daily_usd': 1, 'monthly_usd': 20}
        self.job = {'company': 'Example', 'job_title': 'Data Analyst', 'source_url': 'https://www.builtinnyc.com/job/analyst/123',
                    'location': 'NYC', 'salary': '', 'work_mode': 'Hybrid', 'employment_type': 'Full-time',
                    'posted_date': ws.now()[:10], 'date_evidence': 'Posted today', 'requisition_id': '',
                    'jd': 'SQL reporting required. Snowflake preferred.', 'visa_excerpt': '', 'limitations': ''}

    def imported(self):
        return ws.import_job(self.root, self.db, self.root / 'output', self.resume, self.job)

    def test_search_requires_grounded_posting_url(self):
        response = {'data': {'coverage': [], 'jobs': [self.job], 'summary': 'Limited'}, 'sources': [], 'run_id': 'test'}
        with patch.object(ws, 'structured_call', return_value=response):
            result = ws.discover(self.root, self.db, self.root / 'output', self.resume, self.limits)
        self.assertFalse(result['accepted'])
        self.assertTrue(result['rejected'])
        self.assertFalse(ws.jobs(self.db))

    def test_search_deduplicates_without_resetting_status(self):
        response = {'data': {'coverage': [], 'jobs': [self.job], 'summary': 'Limited'},
                    'sources': [self.job['source_url']], 'run_id': 'test'}
        with patch.object(ws, 'structured_call', return_value=response):
            first = ws.discover(self.root, self.db, self.root / 'output', self.resume, self.limits)
            jid = first['accepted'][0]['id']
            with connect(self.db) as db:
                db.execute('UPDATE jobs SET status=? WHERE id=?', ('REVIEWED', jid))
            second = ws.discover(self.root, self.db, self.root / 'output', self.resume, self.limits)
        self.assertEqual(second['accepted'][0]['id'], jid)
        self.assertEqual(len(ws.jobs(self.db)), 1)
        self.assertEqual(ws.detail(self.db, jid)['status'], 'REVIEWED')

    def test_unknown_visa_is_never_eligible(self):
        self.assertEqual(ws.eligibility_bucket({}), 'Needs verification')
        self.assertEqual(ws.eligibility_bucket({'verification_result': {'visa_grade': 'NO'}}), 'Excluded')

    def test_contract_and_explicit_sponsorship_restrictions_are_excluded(self):
        self.assertEqual(ws.eligibility_bucket({'employment_type': 'Contract'}), 'Excluded')
        self.assertEqual(ws.eligibility_bucket({'visa_excerpt': 'We do not sponsor employment visas.'}), 'Excluded')

    def test_crawl_date_does_not_establish_freshness(self):
        self.job['date_evidence'] = 'Crawled 2 days ago'
        response = {'data': {'coverage': [], 'jobs': [self.job], 'summary': 'Limited'},
                    'sources': [self.job['source_url']], 'run_id': 'test'}
        with patch.object(ws, 'structured_call', return_value=response):
            result = ws.discover(self.root, self.db, self.root / 'output', self.resume, self.limits)
        meta = json.loads(ws.detail(self.db, result['accepted'][0]['id'])['details_json'])
        self.assertEqual(meta['posted_date'], '')
        self.assertEqual(meta['freshness'], 'UNKNOWN')

    def test_bullet_new_metric_or_technology_blocked(self):
        facts = read_resume(self.resume)['facts']
        for text in ('Built 40 SQL reports.', 'Built 4 SQL and Snowflake reports.'):
            with self.assertRaises(ValueError):
                ws.validate_bullets([{'source_id': 'P005', 'text': text, 'why': 'JD'}], facts)

    def test_bullet_cannot_reference_header(self):
        with self.assertRaises(ValueError):
            ws.validate_bullets([{'source_id': 'P001', 'text': 'Led a team.', 'why': ''}], read_resume(self.resume)['facts'])

    def test_independent_check_reverts_unsupported_rewrite_and_stale_approval(self):
        jid = self.imported()
        generated = {'data': {'bullets': [{'source_id': 'P005', 'text': 'Led reporting with 4 SQL reports.', 'why': 'Emphasize reporting'}]},
                     'run_id': 'g', 'estimated_cost_usd': .001}
        audited = {'data': {'checks': [{'index': 0, 'supported': False, 'reason': 'Leadership is not supported.'}]},
                   'run_id': 'a', 'estimated_cost_usd': .001}
        with patch.object(ws, 'structured_call', side_effect=[generated, audited]):
            vid = ws.generate_bullets(self.root, self.db, self.limits, self.resume, jid)
        with connect(self.db) as db:
            result = json.loads(db.execute('SELECT result_json FROM bullet_versions WHERE id=?', (vid,)).fetchone()[0])
        self.assertEqual(result['bullets'][0]['text'], 'Reporting: Built 4 SQL reports.')
        ws.save_full_jd(self.db, jid, 'Changed job requirements')
        with self.assertRaises(ValueError):
            ws.approve_version(self.db, self.resume, vid)

    def test_semantic_score_uses_evidence_and_weights(self):
        jid = self.imported()
        result = {'summary': 'Test', 'requirements': [
            {'requirement': 'SQL', 'category': 'strong', 'source_ids': ['P005'], 'reason': 'Reports', 'resume_action': 'Emphasize', 'importance': 2},
            {'requirement': 'Snowflake', 'category': 'gap', 'source_ids': [], 'reason': 'No evidence', 'resume_action': 'Do not add', 'importance': 1}],
            'recommended_emphasis': ['SQL'], 'questions': [], 'eligibility': {}}
        with patch.object(ws, 'structured_call', return_value={'data': result, 'run_id': 'a', 'estimated_cost_usd': .001}):
            a = ws.analyze_job(self.root, self.db, self.limits, self.resume, jid)
        self.assertEqual(a['score'], 67)
        self.assertEqual(a['requirements'][0]['evidence'][0]['text'], 'Reporting: Built 4 SQL reports.')

    def test_closed_posting_excluded(self):
        self.assertEqual(ws.eligibility_bucket({'verification_result': {'open_status': 'CLOSED'}}), 'Excluded')
