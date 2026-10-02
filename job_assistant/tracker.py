import sqlite3
from contextlib import contextmanager

STATUSES = ('NEW', 'REVIEWED', 'READY_TO_APPLY', 'APPLIED', 'INTERVIEW', 'REJECTED', 'SKIPPED')


@contextmanager
def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY, company TEXT, job_title TEXT, job_url TEXT,
        date_found TEXT NOT NULL, salary TEXT, location TEXT,
        match_score INTEGER NOT NULL CHECK(match_score BETWEEN 0 AND 100),
        status TEXT NOT NULL CHECK(status IN ('NEW','REVIEWED','READY_TO_APPLY','APPLIED','INTERVIEW','REJECTED','SKIPPED')),
        notes TEXT NOT NULL DEFAULT '', tailored_resume_path TEXT NOT NULL,
        analysis_path TEXT NOT NULL, analysis_json TEXT NOT NULL)''')
    db.commit()
    try:
        with db:
            yield db
    finally:
        db.close()


def save(db, analysis, directory, date, notes):
    import json
    with db:
        cursor = db.execute('''INSERT INTO jobs
          (company,job_title,job_url,date_found,salary,location,match_score,status,notes,
           tailored_resume_path,analysis_path,analysis_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
          (analysis['company'], analysis['job_title'], analysis['job_url'], date,
           analysis['salary'], analysis['location'], analysis['overall_match_score'], 'NEW', notes,
           str(directory / 'tailored_resume.md'), str(directory / 'analysis.json'),
           json.dumps(analysis, ensure_ascii=False)))
    return cursor.lastrowid
