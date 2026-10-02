import argparse
import os
import json
from pathlib import Path
import sqlite3
import sys
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError
from .tracker import STATUSES, connect
from .service import analyze_and_save, report

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESUME = ROOT / 'private/Master Resume.docx' if (ROOT / 'private/Master Resume.docx').exists() else ROOT / 'private/master_resume.txt'


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Local evidence-first job assistant; no applications or network calls.')
    parser.add_argument('--db', type=Path, default=ROOT / 'data/jobs.sqlite3')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('analyze', help='Analyze a UTF-8 job description and save a NEW tracker row')
    run.add_argument('job_description', type=Path)
    run.add_argument('--resume', type=Path, default=Path(os.environ.get('JOB_ASSISTANT_RESUME', DEFAULT_RESUME)))
    run.add_argument('--output-dir', type=Path, default=ROOT / 'output')
    for key in ('company', 'job-title', 'job-url', 'salary', 'location', 'work-mode'):
        run.add_argument('--' + key)
    run.add_argument('--notes', default='')
    run.add_argument('--json', action='store_true', help='Print full structured result instead of Markdown')
    listing = commands.add_parser('list', help='List tracked analyses')
    listing.add_argument('--status', choices=STATUSES)
    show = commands.add_parser('show', help='Show saved analysis')
    show.add_argument('id', type=int)
    update = commands.add_parser('update', help='Manually change a tracker row; never submits anything')
    update.add_argument('id', type=int)
    update.add_argument('--status', choices=STATUSES)
    update.add_argument('--notes')
    args = parser.parse_args(argv)
    try:
        if args.command == 'analyze':
            text = args.job_description.read_text(encoding='utf-8-sig')
            result = analyze_and_save(text, args.resume, args.db, args.output_dir, vars(args), args.notes)
            row_id = result['tracker_id']
            directory = result['output_directory']
            a = {k: v for k, v in result.items() if k not in {'tracker_id', 'output_directory'}}
            if args.json:
                print(json.dumps({'tracker_id': row_id, 'output_directory': str(directory), **a}, ensure_ascii=False, indent=2))
            else:
                print(report(a))
                print(f'Tracker ID: {row_id}\nOutput: {directory}')
        else:
            with connect(args.db.resolve()) as db:
                if args.command == 'list':
                    query = 'SELECT id,company,job_title,match_score,status,date_found FROM jobs'
                    rows = db.execute(query + (' WHERE status=?' if args.status else '') + ' ORDER BY id DESC', (args.status,) if args.status else ())
                    print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
                else:
                    row = db.execute('SELECT * FROM jobs WHERE id=?', (args.id,)).fetchone()
                    if row is None:
                        raise ValueError(f'No tracker row with ID {args.id}.')
                    if args.command == 'show':
                        item = dict(row)
                        item['analysis_json'] = json.loads(item['analysis_json'])
                        print(json.dumps(item, ensure_ascii=False, indent=2))
                    else:
                        if args.status is None and args.notes is None:
                            raise ValueError('Supply --status and/or --notes.')
                        db.execute('UPDATE jobs SET status=?,notes=? WHERE id=?',
                                   (args.status or row['status'], args.notes if args.notes is not None else row['notes'], args.id))
                        print(f'Updated tracker row {args.id}.')
        return 0
    except (OSError, ValueError, sqlite3.Error, BadZipFile, ParseError, KeyError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2
