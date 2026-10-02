"""English Streamlit job inbox and evidence-linked bullet editor."""
import json
from pathlib import Path
import streamlit as st
from job_assistant.i18n import t, option_labels
from . import workspace as ws
from .tracker import connect
from .resume import read_resume
from .api_model import usage


def render(root, db_path, output, resume_path):
    ws.initialize(db_path)
    config = json.loads((root / 'agent-config.json').read_text(encoding='utf-8'))
    limits = config['budget']
    st.title(t('Job inbox'))
    st.write(t('Discover opportunities, inspect gaps, and create source-linked resume bullets in one place.'))
    st.caption(t('Search uses public indexed pages, not logged-in scraping. Results are candidates, not verified eligibility. No applications are submitted.'))
    with st.expander(t('Search preferences and coverage')):
        st.write(ws.PREFERENCES)
        st.write(t('Sources: LinkedIn, Indeed, Built In NYC. Rolling seven-day window. A manual search is capped at three web tool calls; it cannot exhaust all listings.'))
        costs = usage(db_path)
        st.text(t("Today's estimated cost plus reservations: ${cost:.4f} / ${limit:.2f}", cost=costs['day'], limit=limits['daily_usd']))
    if st.button(t('Search recent jobs'), type='primary', key='discover_jobs'):
        with st.spinner(t('Searching the three discovery platforms...')):
            result = ws.discover(root, db_path, output, resume_path, limits)
        st.success(t('Saved or refreshed {count} candidates. Review coverage below.', count=len(result['accepted'])))
    with connect(Path(db_path)) as db:
        runs = [dict(r) for r in db.execute('SELECT * FROM search_runs ORDER BY id DESC LIMIT 5')]
        unattached = [dict(r) for r in db.execute('SELECT id,company,job_title FROM jobs WHERE id NOT IN (SELECT job_id FROM job_details) ORDER BY id DESC')]
    if runs:
        with st.expander(t('Recent search runs and limitations'), expanded=not ws.jobs(db_path)):
            for run in runs:
                st.write(f"{run['started']} — {run['status']}")
                if run['result_json'] != '{}':
                    r = json.loads(run['result_json'])
                    st.write(r['data'].get('summary', ''))
                    st.dataframe(r['data'].get('coverage', []), hide_index=True)
                    if r.get('rejected'):
                        st.write(t('Not imported:'), r['rejected'])
    if unattached:
        with st.expander(t('Bring an existing tracked job into this workspace')):
            lookup = {r['id']: r for r in unattached}
            chosen = st.selectbox(t('Tracked job'), list(lookup), format_func=lambda i: f"#{i} {lookup[i]['company']} - {lookup[i]['job_title']}", key='ui_Tracked job')
            if st.button(t('Add tracked job to inbox'), key='ui_Add tracked job to inbox'):
                ws.adopt_tracked_job(db_path, chosen)
                st.rerun()
    rows = ws.jobs(db_path)
    if not rows:
        st.info(t('Run a search or add a tracked job to begin.'))
        return
    scope = st.selectbox(t('Eligibility filter'), ['Needs verification', 'All candidates', 'Excluded'], format_func=option_labels(), key='ui_Eligibility filter')
    visible = [r for r in rows if scope == 'All candidates' or ws.eligibility_bucket(json.loads(r['details_json'])) == scope]
    cards = []
    for row in visible:
        meta = json.loads(row['details_json'])
        analysis = json.loads(row['semantic_json']) if row['semantic_json'] else {}
        cards.append({'ID': row['id'], 'Company': row['company'], 'Role': row['job_title'],
                      'Location': row['location'] or 'Unknown', 'Salary': row['salary'] or 'Unknown',
                      'Eligibility': ws.eligibility_bucket(meta), 'Evidence score': analysis.get('score'),
                      'Main gaps': '; '.join(i['requirement'] for i in analysis.get('requirements', []) if i['category'] in ('gap', 'partial'))[:220],
                      'Date evidence': meta.get('date_evidence', 'Unknown'), 'Status': row['status']})
    st.dataframe([{t(k): t(v) if k in ('Eligibility', 'Status') else v for k, v in card.items()} for card in cards], hide_index=True, width='stretch')
    if not visible:
        return
    lookup = {r['id']: r for r in visible}
    selected = st.selectbox(t('Open job'), list(lookup), format_func=lambda i: f"#{i} {lookup[i]['company']} — {lookup[i]['job_title']}", key='inbox_selection')
    row = lookup[selected]
    metadata = json.loads(row['details_json'])
    st.subheader(f"{row['company']} · {row['job_title']}")
    if row['job_url']:
        st.link_button(t('Original posting'), row['job_url'])
    st.text(f"{row['location'] or 'Location unknown'} · {row['salary'] or 'Salary unknown'}")
    st.warning(t('Eligibility is not confirmed. H-1B transfer support, full-time status, current availability, and location require evidence.'))
    for reason in ws.exclusion_reasons(metadata):
        st.error(t('Excluded') + ': ' + reason)
    overview, match, bullets = st.tabs([t('Job details and eligibility'), t('Matches, gaps and changes'), t('Tailored bullets')])
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
            st.json(metadata['verification_result'])
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
            st.write(t('Recommended emphasis'), a['recommended_emphasis'])
            st.write(t('Eligibility questions'), a['eligibility'])
            st.write(t('Questions for review'), a['questions'])
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
