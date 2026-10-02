"""Shared analysis and persistence used by CLI and local UI."""
from datetime import datetime
import json
from pathlib import Path
import shutil
from uuid import uuid4
from .analysis import analyze, matches, metadata
from .resume import read_resume, tailor
from .tracker import connect, save

def report(a):
    lines = [f"# {a['company'] or 'Company not confirmed'} — {a['job_title'] or 'Job title not confirmed'}",
             f"Match score: {a['overall_match_score']}/100(evidence coverage for recognized concepts)",
             a['score_explanation'], f"Manual review recommended: {a['deserves_manual_review']}; {a['review_reason']}"]
    for key, label in [('strong_matches', 'Strong matches'), ('partial_matches', 'Partial matches'), ('important_gaps', 'Important gaps (no master resume evidence)')]:
        lines.append(f'\n## {label}')
        for item in a[key]:
            lines.append(f"- {item['concept']}: {item['requirement']}")
            for evidence in item['evidence']:
                lines.append(f"  - [{evidence['id']}] {evidence['text']}")
        if not a[key]:
            lines.append('No recognized items.')
    lines += ['\n## Recommended emphasis', ', '.join(a['recommended_resume_emphasis']) or 'Insufficient evidence.', '\n## Preference checks']
    lines += [f'- {k}: {v}' for k, v in a['preferences'].items()]
    lines += ['\n## Questions for your judgment'] + [f'- {q}' for q in a['questions']]
    lines += ['\n## Tailored resume draft', a['tailored_resume_draft']]
    return '\n\n'.join(lines) + '\n'


def analyze_and_save(text, resume_path, db_path, output_dir, overrides=None, notes=""):
    if not text.strip():
        raise ValueError('Job description is empty.')
    resume = read_resume(resume_path)
    a = analyze(text, resume, metadata(text, overrides or {}))
    draft, mapping = tailor(resume, a['recommended_resume_emphasis'], matches)
    a['tailored_resume_draft'] = draft
    a['draft_source_paragraphs'] = mapping
    a['resume_source_facts'] = resume['facts']
    now = datetime.now().astimezone()
    directory = (Path(output_dir) / (now.strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8])).resolve()
    directory.mkdir(parents=True)
    try:
        (directory / 'job_description.txt').write_text(text, encoding='utf-8')
        (directory / 'tailored_resume.md').write_text(draft, encoding='utf-8')
        (directory / 'analysis.json').write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding='utf-8')
        (directory / 'analysis.md').write_text(report(a), encoding='utf-8')
        with connect(Path(db_path).resolve()) as db:
            row_id = save(db, a, directory, now.date().isoformat(), notes)
    except Exception:
        shutil.rmtree(directory)
        raise
    return {"tracker_id": row_id, "output_directory": str(directory), **a}
