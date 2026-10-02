"""Bilingual job inbox with direct selection and evidence-linked review."""
import json
from pathlib import Path
import streamlit as st
from job_assistant.i18n import t, option_labels
from . import workspace as ws
from .tracker import connect
from .resume import read_resume
from .api_model import usage


def select_job(job_id):
    st.session_state['inbox_selection'] = job_id


def render(root, db_path, output, resume_path):
    ws.initialize(db_path)
    config = json.loads((root / 'agent-config.json').read_text(encoding='utf-8'))
    limits = config['budget']
    heading, action = st.columns([4, 1], vertical_alignment='center')
    with heading:
        st.title(t('Job inbox'))
        st.caption(t('Click a role. Review the fit. Shape your resume.'))
    with action:
        if st.button(t('Search recent jobs'), type='primary', key='discover_jobs', width='stretch'):
            with st.spinner(t('Searching the three discovery platforms...')):
                result = ws.discover(root, db_path, output, resume_path, limits)
            st.success(t('Saved or refreshed {count} candidates. Review coverage below.', count=len(result['accepted'])))
    rows = ws.jobs(db_path)
    pending = sum(ws.eligibility_bucket(json.loads(r['details_json'])) != 'Excluded' for r in rows)
    summary = st.columns(3)
    summary[0].metric(t('All records'), len(rows))
    summary[1].metric(t('Needs verification'), pending)
    summary[2].metric(t('Excluded'), len(rows) - pending)
    with st.expander(t('Search settings and history')):
        st.write(ws.PREFERENCES)
        st.caption(t('Search uses public indexed pages, not logged-in scraping. Results are candidates, not verified eligibility. No applications are submitted.'))
        costs = usage(db_path)
        st.text(t("Today's estimated cost plus reservations: ${cost:.4f} / ${limit:.2f}", cost=costs['day'], limit=limits['daily_usd']))
        with connect(Path(db_path)) as db:
            runs = [dict(r) for r in db.execute('SELECT * FROM search_runs ORDER BY id DESC LIMIT 5')]
            unattached = [dict(r) for r in db.execute('SELECT id,company,job_title FROM jobs WHERE id NOT IN (SELECT job_id FROM job_details) ORDER BY id DESC')]
        for run in runs:
            st.caption(f"{run['started']} — {run['status']}")
            if run['result_json'] != '{}':
                result = json.loads(run['result_json'])
                st.write(result['data'].get('summary', ''))
                st.dataframe(result['data'].get('coverage', []), hide_index=True)
                if result.get('rejected'):
                    st.write(t('Not imported:'), result['rejected'])
        for record in unattached:
            if st.button(t('Add tracked job to inbox') + f" · {record['company']} — {record['job_title']}", key=f"attach_{record['id']}"):
                ws.adopt_tracked_job(db_path, record['id'])
                st.rerun()
    if not rows:
        st.info(t('Run a search or add a tracked job to begin.'))
        return
    filters, search = st.columns([3, 2], vertical_alignment='bottom')
    with filters:
        scope = st.radio(t('Eligibility filter'), ['Needs verification', 'All candidates', 'Excluded'],
                         format_func=option_labels(), key='ui_Eligibility filter', horizontal=True, label_visibility='collapsed')
    with search:
        query = st.text_input(t('Search company or role'), key='inbox_query', placeholder=t('Search company or role'), label_visibility='collapsed').strip().lower()
    visible = [r for r in rows if (scope == 'All candidates' or ws.eligibility_bucket(json.loads(r['details_json'])) == scope)
               and (not query or query in (r['company'] + ' ' + r['job_title'] + ' ' + (r['location'] or '')).lower())]
    visible.sort(key=lambda r: (json.loads(r['semantic_json']).get('score', -1) if r['semantic_json'] else -1, r['id']), reverse=True)
    if not visible:
        st.info(t('No roles match these filters. Try another filter or search.'))
        return
    lookup = {r['id']: r for r in visible}
    if st.session_state.get('inbox_selection') not in lookup:
        st.session_state['inbox_selection'] = visible[0]['id']
    selected = st.session_state['inbox_selection']
    listing, details = st.columns([1, 1.85], gap='large')
    with listing:
        st.caption(t('{count} roles · highest evidence score first', count=len(visible)))
        with st.container(height=760, border=False, key='job_list'):
            for row in visible:
                analysis = json.loads(row['semantic_json']) if row['semantic_json'] else {}
                metadata = json.loads(row['details_json'])
                score = str(analysis['score']) + '/100' if 'score' in analysis else t('Not analyzed')
                with st.container(border=True, key=f"job_card_{'active' if row['id'] == selected else 'idle'}_{row['id']}"):
                    st.button(f"{row['company']} · {score}\n\n{row['job_title']}", key=f"open_job_{row['id']}",
                              on_click=select_job, args=(row['id'],), width='stretch', type='tertiary')
                    st.caption((row['location'] or t('Unknown')) + ' · ' + metadata.get('work_mode', t('Unknown')))
                    st.text(row['salary'] or t('Salary unknown'))
                    requirements = analysis.get('requirements', [])
                    gaps = [i['requirement'] for category in ('gap', 'partial') for i in requirements if i['category'] == category]
                    if gaps:
                        st.caption(t('Main gaps') + ': ' + '; '.join(gaps[:2]))
                    st.caption(t(ws.eligibility_bucket(metadata)))
    with details:
        with st.container(border=True, key='job_detail'):
            render_detail(root, db_path, limits, resume_path, lookup[selected])


def render_detail(root, db_path, limits, resume_path, row):
    selected = row['id']
    metadata = json.loads(row['details_json'])
    st.subheader(f"{row['company']} · {row['job_title']}")
    if row['job_url']:
        st.link_button(t('Original posting'), row['job_url'])
    st.text(f"{row['location'] or 'Location unknown'} · {row['salary'] or 'Salary unknown'}")
    st.warning(t('Eligibility is not confirmed. H-1B transfer support, full-time status, current availability, and location require evidence.'))
    for reason in ws.exclusion_reasons(metadata):
        st.error(t('Excluded') + ': ' + reason)
    match, bullets, overview = st.tabs([t('Matches, gaps and changes'), t('Tailored bullets'), t('Job details and eligibility')])
    with overview:
        st.write(t('Content coverage:'), metadata.get('content_kind', 'Unknown'))
        st.write(t('Posting date evidence:'), metadata.get('date_evidence') or 'Unknown')
        st.write(t('Source limitations:'), metadata.get('limitations') or 'Not recorded')
        with st.expander(t('Stored job description'), expanded=True):
            st.text(row['jd'])
        if st.button(t('Verify official posting and visa evidence'), key=f'verify_{selected}'):
            with st.spinner(t('Checking the official posting and employer evidence...')):
                ws.verify_job(root, db_path, limits, selected)
            st.rerun()
        if metadata.get('verification_result'):
            st.caption(t('Web-assisted verification report; review sources before relying on it. Historical sponsorship is not a promise for this role.'))
            for field, value in metadata['verification_result'].items():
                if value:
                    st.caption(field.replace('_', ' ').title())
                    st.text(str(value))
            with st.expander(t('Verification sources')):
                for url in metadata.get('verification_sources', []):
                    if url.startswith('https://'):
                        st.link_button(url, url)
        with st.form(f'full_jd_{selected}'):
            full = st.text_area(t('Paste or update the full JD'), value=row['jd'], height=180, key=f'full_jd_text_{selected}')
            if st.form_submit_button(t('Save JD and invalidate old analysis')):
                ws.save_full_jd(db_path, selected, full)
                st.rerun()
    with match:
        if st.button(t('Analyze requirements and gaps'), key=f'analyze_{selected}', type='primary'):
            with st.spinner(t('Comparing each material requirement with the master resume...')):
                ws.analyze_job(root, db_path, limits, resume_path, selected)
            st.rerun()
        if row['semantic_json']:
            a = json.loads(row['semantic_json'])
            if a['resume_hash'] != read_resume(resume_path)['sha256'] or a['jd_hash'] != row['jd_hash']:
                st.warning(t('This analysis is stale. Reanalyze against the current resume and JD.'))
            st.metric(t('Requirement evidence score'), f"{a['score']} / 100")
            st.caption(t('Weighted model-assessed evidence coverage, not hiring probability or visa eligibility. Unknown requirements count as zero. Review all source evidence.'))
            st.write(a['summary'])
            for item in a['requirements']:
                with st.expander(f"{t(item['category'].upper())} — {item['requirement']}"):
                    st.write(item['reason'])
                    st.write(t('Resume action:'), item['resume_action'])
                    for evidence in item['evidence']:
                        st.text(f"[{evidence['id']}] {evidence['text']}")
            st.subheader(t('Recommended emphasis'))
            for value in a['recommended_emphasis']:
                st.text('\u2022 ' + value)
            with st.expander(t('Eligibility questions')):
                for field, value in a['eligibility'].items():
                    st.caption(t(field.replace('_', ' ').title()))
                    st.text(value)
            st.subheader(t('Questions for review'))
            for value in a['questions']:
                st.text('\u2022 ' + value)
        else:
            st.info(t('Click Analyze to see requirement-level matches, gaps, and suggested resume changes.'))
    with bullets:
        st.caption(t('One click generates up to six bullets, checks metrics and known technologies, and runs an independent model fact check. Review is still required. Each bullet stays with its original role.'))
        with st.form(f'bullets_{selected}'):
            feedback = st.text_area(t('Revision instructions (optional)'), placeholder=t('Emphasize retail margin analysis; keep prototype scope explicit.'), key=f'bullet_feedback_{selected}')
            if st.form_submit_button(t('Generate tailored bullets'), type='primary'):
                with st.spinner(t('Drafting and checking every bullet against its source...')):
                    ws.generate_bullets(root, db_path, limits, resume_path, selected, feedback)
                st.rerun()
        with connect(Path(db_path)) as db:
            versions = [dict(r) for r in db.execute('SELECT * FROM bullet_versions WHERE job_id=? ORDER BY id DESC', (selected,))]
        if versions:
            version_map = {r['id']: r for r in versions}
            version_id = st.selectbox(t('Bullet version'), list(version_map), format_func=lambda i: f"v{i} — {version_map[i]['created']}", key=f'bullet_version_{selected}')
            v = version_map[version_id]
            stale = v['resume_hash'] != read_resume(resume_path)['sha256'] or v['jd_hash'] != row['jd_hash']
            if stale:
                st.warning(t('This version uses an older resume or JD. Generate a new version before approval.'))
            result = json.loads(v['result_json'])
            for index, b in enumerate(result['bullets']):
                st.caption(b['role_context'] + ' · ' + b['source_id'])
                left, right = st.columns(2)
                left.text_area(t('Original'), b['source_text'], disabled=True, key=f"original_{version_id}_{index}")
                right.text_area(t('Suggested bullet'), b['text'], disabled=True, key=f"suggested_{version_id}_{index}")
                st.write(t('Why:'), b['why'])
                st.caption(t('Fact check:') + ' ' + b['verification'])
            if v['approved'] and not stale:
                st.success(t('You approved this version for resume editing. This does not authorize an application.'))
            elif not stale and st.button(t('Approve this bullet version'), key=f'approve_{version_id}'):
                ws.approve_version(db_path, resume_path, version_id)
                st.rerun()
            download = '\n\n'.join(f"### {b['role_context']}\n- {b['text']}\n\nSource: {b['source_id']}" for b in result['bullets'])
            st.download_button(t('Download bullet draft'), download, file_name=f'job-{selected}-bullets-v{version_id}.md', key='ui_Download bullet draft')
