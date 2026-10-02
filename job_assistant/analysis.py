"""Transparent conservative keyword evidence, not an ATS or hiring prediction."""
import re

# Aliases only name equivalent concepts. No substitution between BI/cloud tools.
CONCEPTS = {
    'SQL': ['sql', 't-sql'], 'Python': ['python'], 'Power BI': ['power bi', 'powerbi'],
    'Microsoft Fabric': ['microsoft fabric'], 'Tableau': ['tableau'],
    'DAX': ['dax'], 'Power Query': ['power query'], 'ETL': ['etl', 'extract transform load'],
    'data modeling': ['data modeling', 'data modelling'],
    'data validation': ['data validation'], 'data governance': ['data governance'],
    'analytics engineering': ['analytics engineering', 'analytics engineer'],
    'retail': ['retail'], 'consumer analytics': ['consumer analytics', 'consumer experience'],
    'inventory analytics': ['inventory'], 'commercial analytics': ['commercial analytics'],
    'sales analytics': ['sales'], 'margin analytics': ['margin'],
    'stakeholder collaboration': ['stakeholder', 'stakeholders'],
    'automation': ['automation', 'automated', 'automate', 'automations'],
    'generative AI': ['generative ai', 'llm', 'llms'], 'DuckDB': ['duckdb'],
    'lakehouse': ['lakehouse'], 'Pandas': ['pandas'], 'NumPy': ['numpy'],
    'Streamlit': ['streamlit'], 'SharePoint': ['sharepoint'],
    'dbt': ['dbt'], 'Snowflake': ['snowflake'], 'Databricks': ['databricks'],
    'Spark': ['spark', 'pyspark'], 'Airflow': ['airflow'], 'AWS': ['aws', 'amazon web services'],
    'Azure': ['azure'], 'GCP': ['gcp', 'google cloud'], 'Looker': ['looker'],
    'Excel': ['excel'], 'R': ['r'], 'A/B testing': ['a/b testing', 'ab testing'],
    'machine learning': ['machine learning'], 'statistics': ['statistics', 'statistical'],
    'people management': ['people management', 'manage a team', 'direct reports'],
}


def matches(term, text):
    return any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I)
               for alias in CONCEPTS[term])


def metadata(text, overrides):
    labels = {'company': 'company', 'job_title': 'job title|title', 'job_url': 'job url|url',
              'salary': 'salary|compensation|base salary', 'location': 'location',
              'work_mode': 'work mode|work arrangement'}
    result = {}
    for key, label in labels.items():
        match = re.search(r'^(?:' + label + r')\s*:\s*(.+)$', text, re.I | re.M)
        result[key] = overrides.get(key) or (match.group(1).strip() if match else None)
    return result


def analyze(text, resume, meta):
    requirements, unresolved = [], []
    section = ''
    for raw in text.splitlines():
        line = raw.strip(' \t-*•')
        if not line or re.match(r'^(company|job title|title|job url|url|salary|compensation|base salary|location|work mode|work arrangement):', line, re.I):
            continue
        if re.fullmatch(r'(requirements|qualifications|minimum qualifications|required|preferred|nice to have|responsibilities|about us|benefits)\s*:?', line, re.I):
            section = line.lower().rstrip(':')
            continue
        terms = [term for term in CONCEPTS if matches(term, line)]
        optional = section in {'preferred', 'nice to have'} or bool(re.search(r'\b(preferred|nice.to.have|bonus|optional)\b', line, re.I))
        ambiguous = bool(re.search(r'\b(or|not|no|without)\b|\d+\+?\s*(?:years?|yrs?)|\b(senior|expert|advanced|proficien|bachelor|master|phd|degree|visa|sponsorship|clearance|certif)', line, re.I))
        if not terms or ambiguous:
            unresolved.append(line)
        for term in terms:
            evidence = [f for f in resume['facts'] if matches(term, f['text'])]
            # Skill lists and summaries establish mentions, not delivered projects.
            project = [f for f in evidence if f['section'] in {'experience', 'professional experience'} and ':' in f['text']]
            category = 'strong' if project and not ambiguous else 'partial' if evidence else 'gap'
            requirements.append({'requirement': line, 'concept': term, 'weight': 1 if optional else 2,
                                 'optional': optional, 'category': category,
                                 'evidence': [{'id': f['id'], 'text': f['text']} for f in (project or evidence)],
                                 'caveat': 'Keyword evidence only; qualifiers need judgment.' if ambiguous else None})
    # Repeated keywords do not inflate the score. Keep every source line in requirements.
    grouped = {}
    for item in requirements:
        previous = grouped.get(item['concept'])
        if previous is None or (item['weight'], item['category'] == 'partial') > (previous['weight'], previous['category'] == 'partial'):
            grouped[item['concept']] = item
    scored = list(grouped.values())
    denominator = sum(x['weight'] for x in scored)
    score = round(100 * sum(x['weight'] * {'strong': 1, 'partial': .5, 'gap': 0}[x['category']] for x in scored) / denominator) if denominator else 0
    gaps = [x for x in scored if x['category'] == 'gap']
    questions = [f'Verify the original job requirement: {line}' for line in dict.fromkeys(unresolved)]
    for field in ('company', 'job_title', 'salary', 'location', 'work_mode'):
        if not meta.get(field):
            questions.append(f'Provide or confirm {field}; it could not be reliably identified.')
    location = meta.get('location') or ''
    mode = meta.get('work_mode') or ''
    salary = meta.get('salary') or ''
    preferences = {
        'location': 'NYC/metro keyword found; verify commute' if re.search(r'new york|nyc|brooklyn|queens|jersey city|hoboken|long island|westchester', location, re.I) else 'Unknown or outside preference; verify manually',
        'hybrid': 'Hybrid mentioned; confirm schedule' if 'hybrid' in mode.lower() else 'Hybrid preference not confirmed',
        'salary': f'{salary or "Unknown"}; manually confirm annual USD base >= $100,000 (not bonus/total compensation)',
    }
    questions.append('Confirm annual USD base salary, commute, hybrid arrangement, and role seniority.')
    worthy = score >= 60 and bool(scored)
    return {**meta, 'overall_match_score': score, 'score_type': 'recognized_concept_evidence_coverage',
            'score_explanation': 'Project evidence=1; skill/summary mention or ambiguous requirement=0.5; no evidence=0. General requirements weigh 2; preferred requirements weigh 1. Concepts are deduplicated. Unparsed text is excluded and requires manual review. This is not a hiring probability.',
            'score_confidence': 'limited' if unresolved or not scored else 'keyword_only',
            'scored_concepts': len(scored), 'requirements': requirements,
            'strong_matches': [x for x in scored if x['category'] == 'strong'],
            'partial_matches': [x for x in scored if x['category'] == 'partial'],
            'important_gaps': gaps, 'unresolved_requirements': list(dict.fromkeys(unresolved)),
            'relevant_experience': list({f['id']: f for x in scored for f in x['evidence']}.values()),
            'recommended_resume_emphasis': [x['concept'] for x in scored if x['category'] != 'gap'],
            'deserves_manual_review': worthy,
            'review_reason': 'Evidence coverage is at least 60; manual review is recommended.' if worthy else 'Evidence coverage is below 60 or requirements could not be recognized. Lower priority; check for parsing omissions.',
            'human_review_required': True, 'preferences': preferences, 'questions': questions,
            'master_resume': {'path': resume['path'], 'sha256': resume['sha256']}}
