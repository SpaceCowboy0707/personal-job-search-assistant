"""Local Streamlit front end. Start with run-ui.ps1."""
import json
import os
from pathlib import Path
import sqlite3
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import streamlit as st
from job_assistant.i18n import t, language_switch, option_labels

from job_assistant.resume import read_resume
from job_assistant.service import analyze_and_save, report
from job_assistant.tracker import STATUSES, connect
from job_assistant.api_model import api_key, advise, usage
from job_assistant.workspace_ui import render as render_workspace

ROOT = Path(__file__).resolve().parent
DEFAULT_RESUME = ROOT / 'private/Master Resume.docx' if (ROOT / 'private/Master Resume.docx').exists() else ROOT / 'private/master_resume.txt'
DB = Path(os.environ.get('JOB_ASSISTANT_DB', ROOT / 'data/jobs.sqlite3'))
OUTPUT = Path(os.environ.get('JOB_ASSISTANT_OUTPUT', ROOT / 'output'))
ERRORS = (OSError, ValueError, sqlite3.Error, BadZipFile, ParseError, KeyError)

st.set_page_config(page_title='Job Search Workspace', page_icon='🧭', layout='wide')
st.markdown('''<style>
.block-container {max-width: 1240px; padding-top: 4rem;}
.st-key-language_switch {position: fixed; top: 0.5rem; right: 9rem; width: auto; z-index: 1000000;}
[data-testid="stMetric"] {background: #f0f5f4; border: 1px solid #dce6e2; border-radius: 12px; padding: 16px;}
[data-testid="stSidebar"] {border-right: 1px solid #dce6e2;}
</style>''', unsafe_allow_html=True)
language_switch()


def show_result(a, prefix):
    st.subheader(f"{a.get('company') or 'Company not confirmed'} · {a.get('job_title') or 'Job title not confirmed'}")
    cols = st.columns(4)
    cols[0].metric(t('Evidence coverage'), f"{a['overall_match_score']} / 100")
    cols[1].metric(t('Strong matches'), len(a['strong_matches']))
    cols[2].metric(t('Partial matches'), len(a['partial_matches']))
    cols[3].metric(t('Missing evidence'), len(a['important_gaps']))
    st.info(a['review_reason'])
    st.caption(t('Scores measure keyword evidence coverage, not hiring probability. Review seniority, years of experience, and unrecognized requirements manually.'))
    evidence, draft, judgment = st.tabs([t('Matches and evidence'), t('Tailored resume'), t('Preferences and questions')])
    with evidence:
        for field, label in [('strong_matches', 'Strong matches'), ('partial_matches', 'Partial matches'), ('important_gaps', 'No evidence in the master resume')]:
            st.markdown(f'#### {t(label)}')
            if not a[field]:
                st.caption(t('No recognized items'))
            for item in a[field]:
                with st.expander(item['concept']):
                    st.text(item['requirement'])
                    for fact in item['evidence']:
                        st.text(f"[{fact['id']}] {fact['text']}")
                    if item.get('caveat'):
                        st.caption(item['caveat'])
        st.markdown(t('#### Recommended emphasis'))
        st.write(' · '.join(a['recommended_resume_emphasis']) or 'No suggestions')
        with st.expander(t('Scoring rules and sources')):
            st.write(a['score_explanation'])
            st.json(a['master_resume'])
    with draft:
        st.caption(t('Only original experience bullets within the same role are reordered. All facts come from the master resume.'))
        st.text_area(t('Draft preview'), a['tailored_resume_draft'], height=460, disabled=True, key=f'{prefix}_draft')
        st.download_button(t('Download resume draft - Markdown'), a['tailored_resume_draft'], file_name='tailored_resume.md', mime='text/markdown', key=f'{prefix}_resume_download')
    with judgment:
        for field, label in [('location', 'Location'), ('salary', 'Salary'), ('work_mode', 'Work arrangement')]:
            st.write(f"**{t(label)}: ** {a.get(field) or 'Not confirmed'}")
        for value in a['preferences'].values():
            st.write(value)
        st.markdown(t('#### Questions for your judgment'))
        for question in a['questions']:
            st.text('• ' + question)
    left, right = st.columns(2)
    left.download_button(t('Download full report'), report(a), file_name='analysis.md', mime='text/markdown', key=f'{prefix}_report')
    right.download_button(t('Download analysis JSON'), json.dumps(a, ensure_ascii=False, indent=2), file_name='analysis.json', mime='application/json', key=f'{prefix}_json')


with st.sidebar:
    st.markdown(t('### 🧭 Job Search Workspace'))
    st.caption(t('From job descriptions to evidence-backed resume drafts'))
    st.caption(t('Interface language only; job descriptions, analysis text and resume drafts retain their original language.'))
    page = st.radio(t('Workspace'), ['Analyze a job', 'Job inbox', 'Job tracker', 'Master resume', 'Agent settings and trial'], label_visibility='collapsed', format_func=option_labels(), key='ui_Workspace')
    st.divider()
    st.markdown(t('**Your preferences**'))
    st.caption(t('NYC / NYC metro · Hybrid preferred\n\nAbout $100,000+ base salary\n\nData / BI / Business Analytics\nAnalytics Engineering · Retail / AI'))
    with st.expander(t('Master resume settings')):
        resume_path = st.text_input(t('Local master resume path'), os.environ.get('JOB_ASSISTANT_RESUME', str(DEFAULT_RESUME)), key='resume_path')
        st.caption(t('Supports DOCX / TXT / MD. This file is read when analysis runs.'))
    st.divider()
    st.caption(t('Master resume is the source of truth\n\nApplications are submitted manually'))

if page == 'Analyze a job':
    st.title(t('Find your next opportunity'))
    st.write(t('Paste a job description, review the evidence, and generate a resume draft.'))
    if st.button(t('Load fictional example'), key='load_example'):
        st.session_state['jd_text'] = (ROOT / 'examples/job_description.txt').read_text(encoding='utf-8')
    with st.form('analyze_form'):
        mode = st.radio(t('Job input method'), ['Paste text', 'Upload file'], horizontal=True, format_func=option_labels(), key='ui_Job input method')
        jd = st.text_area(t('Job description'), height=260, key='jd_text', placeholder=t('Paste the full English JD. Company, Job title, and Location labels are recommended.'))
        upload = st.file_uploader(t('Or upload UTF-8 TXT / MD'), type=['txt', 'md'], key='ui_Or upload UTF-8 TXT / MD')
        with st.expander(t('Job details (optional; override JD labels)')):
            left, right = st.columns(2)
            company = left.text_input(t('Company'), key='ui_Company')
            title = right.text_input(t('Job title'), key='ui_Job title')
            location = left.text_input(t('Location'), key='ui_Location')
            salary = right.text_input(t('Base salary'), key='ui_Base salary')
            url = left.text_input(t('Job URL'), key='ui_Job URL')
            work_mode = right.text_input(t('Work arrangement'), placeholder=t('Hybrid / Remote / On-site'), key='ui_Work arrangement')
            notes = st.text_area(t('Notes'), height=80, key='ui_Notes')
        submitted = st.form_submit_button(t('Analyze and save to tracker'), type='primary')
    if submitted:
        try:
            if mode == 'Upload file':
                if upload is None:
                    raise ValueError('Select a job description file or switch to Paste text.')
                text = upload.getvalue().decode('utf-8-sig')
            else:
                text = jd
            if not text.strip():
                raise ValueError('Enter a job description first.')
            with st.spinner(t('Reading the master resume, checking evidence, and saving...')):
                st.session_state['latest_result'] = analyze_and_save(
                    text, Path(resume_path), DB, OUTPUT,
                    {'company': company.strip(), 'job_title': title.strip(), 'location': location.strip(),
                     'salary': salary.strip(), 'job_url': url.strip(), 'work_mode': work_mode.strip()}, notes)
        except ERRORS as error:
            st.error(t('Analysis failed: {error}', error=error))
    if 'latest_result' in st.session_state:
        result = st.session_state['latest_result']
        st.divider()
        st.success(t('Latest saved analysis - Tracker ID #{id}(click Analyze again after changing the input)', id=result['tracker_id']))
        show_result(result, f"new_{result['tracker_id']}")

elif page == 'Job inbox':
    try:
        render_workspace(ROOT, DB, OUTPUT, Path(resume_path))
    except (*ERRORS, TimeoutError, StopIteration) as error:
        st.error(t('Workspace action failed: {error}', error=error))

elif page == 'Job tracker':
    st.title(t('Job tracker'))
    st.write(t('Manage your analyses and next steps. Shares the same local database with the CLI.'))
    try:
        with connect(DB) as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM jobs ORDER BY id DESC')]
        cols = st.columns(3)
        cols[0].metric(t('All records'), len(rows))
        cols[1].metric(t('Awaiting review'), sum(r['status'] == 'NEW' for r in rows))
        cols[2].metric(t('Ready to apply'), sum(r['status'] == 'READY_TO_APPLY' for r in rows))
        status_filter = st.selectbox(t('Filter by status'), ['All', *STATUSES], format_func=option_labels(), key='ui_Filter by status')
        visible = [r for r in rows if status_filter == 'All' or r['status'] == status_filter]
        if not visible:
            st.info(t('No matching records. Add a job in Analyze a job first.'))
        else:
            st.dataframe([{k: r[k] for k in ('id', 'company', 'job_title', 'match_score', 'status', 'location', 'salary', 'date_found')} for r in visible], hide_index=True, width='stretch')
            by_id = {r['id']: r for r in visible}
            selected = st.selectbox(t('View or edit job'), list(by_id), format_func=lambda i: f"#{i} · {by_id[i]['company'] or 'Company not confirmed'} · {by_id[i]['job_title'] or 'Job title not confirmed'}", key='ui_View or edit job')
            row = by_id[selected]
            with st.form(f'update_{selected}'):
                status = st.selectbox(t('Job status'), STATUSES, index=STATUSES.index(row['status']), format_func=option_labels(), key=f'job_status_{selected}')
                notes = st.text_area(t('Job notes'), value=row['notes'], key=f'job_notes_{selected}')
                if st.form_submit_button(t('Save status and notes'), type='primary'):
                    with connect(DB) as db:
                        db.execute('UPDATE jobs SET status=?, notes=? WHERE id=?', (status, notes, selected))
                    st.session_state['tracker_saved'] = selected
                    st.rerun()
            if st.session_state.pop('tracker_saved', None) is not None:
                st.success(t('Status and notes saved.'))
            if row['job_url']:
                st.text(f"Job URL: {row['job_url']}")
            show_result(json.loads(row['analysis_json']), f'tracker_{selected}')
    except ERRORS as error:
        st.error(t('Could not read or update tracker: {error}', error=error))

elif page == 'Agent settings and trial':
    st.title(t('Agent settings and trial'))
    config = json.loads((ROOT / 'agent-config.json').read_text(encoding='utf-8'))
    st.info(t('Planned schedule: Monday-Friday at 09:00 America/New_York. Scheduled discovery is not enabled. This page provides API analysis suggestions.'))
    st.write(t('Provider: OpenAI API - GPT-5.4 mini. The current master resume and JD are sent to OpenAI only when you click Generate.'))
    try:
        has_key = bool(api_key(ROOT))
    except (OSError, ValueError, AttributeError):
        st.error(t('Invalid local key configuration. Check secrets.toml; its contents will not be displayed.'))
        st.stop()
    st.success(t('API key configured (validity not yet checked)')) if has_key else st.warning(t('API key not configured. Follow the README to configure it locally. Do not send your key in chat.'))
    costs = usage(DB)
    cols = st.columns(2)
    cols[0].metric(t('Estimated daily cost / including reservations'), f"${costs['day']:.4f} / ${config['budget']['daily_usd']:.2f}")
    cols[1].metric(t('Estimated monthly cost / including reservations'), f"${costs['month']:.4f} / ${config['budget']['monthly_usd']:.2f}")
    st.caption(t('Budgets cover this tool only, not your account bill. Failed or interrupted requests retain their reservation and are not retried automatically.'))
    st.json(config)
    with st.form('api_model_trial'):
        trial_jd = st.text_area(t('Trial job description'), height=220, key='ui_Trial job description')
        run_trial = st.form_submit_button(t('Generate and save API suggestions'), disabled=not has_key)
    if run_trial:
        try:
            with st.spinner(t('Running API analysis...')):
                resume = read_resume(Path(resume_path))
                advise(ROOT, DB, config['budget'], resume, trial_jd)
            st.rerun()
        except (*ERRORS, TimeoutError) as error:
            st.error(t('Trial failed: {error}', error=error))
    costs = usage(DB)
    if costs['rows']:
        st.dataframe([{k: r[k] for k in ('started', 'status', 'model', 'charge', 'input_tokens', 'output_tokens')} for r in costs['rows']], hide_index=True)
        saved = {r['id']: r for r in costs['rows'] if r['result_json']}
        if saved:
            selected = st.selectbox(t('Saved API suggestions'), list(saved), format_func=lambda i: saved[i]['started'], key='ui_Saved API suggestions')
            st.warning(t('Source text is filled in by the program. Model explanations and gaps may be incorrect. Suggestions do not change your resume or application status.'))
            result = json.loads(saved[selected]['result_json'])
            st.json(result)
            st.download_button(t('Download API suggestions'), json.dumps(result, ensure_ascii=False, indent=2), file_name='api_advice.json', key='ui_Download API suggestions')

else:
    st.title(t('Master resume - Source of truth'))
    st.write(t('Analysis uses only facts in this file. The next analysis rereads any changes to your master resume.'))
    try:
        resume = read_resume(Path(resume_path))
        st.success(t('Loaded {count} source paragraphs', count=len(resume['facts'])))
        st.text(resume['path'])
        for fact in resume['facts']:
            st.caption(fact['id'] + ' · ' + fact['section'])
            st.text(fact['text'])
        with st.expander(t('Source SHA-256')):
            st.code(resume['sha256'])
    except ERRORS as error:
        st.error(t('Could not read master resume: {error}', error=error))
