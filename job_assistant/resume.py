"""Read the source of truth; never generate new resume claims."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def read_resume(path):
    path = Path(path)
    if path.suffix.lower() == '.docx':
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
        paragraphs = []
        for p in root.findall('.//w:body//w:p', NS):
            # Keep tabs between company/location and title/date.
            text = ''.join(n.text or '' if n.tag.endswith('}t') else '\t'
                           for n in p.iter() if n.tag in
                           {'{' + NS['w'] + '}t', '{' + NS['w'] + '}tab'})
            if text.strip():
                paragraphs.append(text.strip())
    elif path.suffix.lower() in {'.txt', '.md'}:
        paragraphs = [p.strip() for p in path.read_text(encoding='utf-8-sig').splitlines() if p.strip()]
    else:
        raise ValueError('Master resume must be DOCX, TXT, or Markdown.')
    if not paragraphs:
        raise ValueError('Master resume contains no readable text.')
    section = 'header'
    facts = []
    for i, text in enumerate(paragraphs):
        heading = text.strip('# ').upper()
        if heading in {'SKILLS', 'PROFESSIONAL EXPERIENCE', 'EXPERIENCE', 'EDUCATION'}:
            section = heading.lower()
        facts.append({'id': f'P{i+1:03}', 'text': text, 'section': section})
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'facts': facts}


def tailor(resume, terms, matcher):
    """Reorder colon-led experience bullets only, within contiguous blocks.

    Employer/title/date paragraphs remain fixed. All content is copied verbatim.
    Unrecognized formats remain unchanged rather than risking mixed employers.
    """
    ordered, block = [], []

    def flush():
        ordered.extend(sorted(block, key=lambda f: -sum(matcher(t, f['text']) for t in terms)))
        block.clear()

    for fact in resume['facts']:
        if fact['section'] in {'professional experience', 'experience'} and ':' in fact['text']:
            block.append(fact)
        else:
            flush()
            ordered.append(fact)
    flush()
    assert sorted(f['id'] for f in ordered) == sorted(f['id'] for f in resume['facts'])
    return '\n\n'.join(f['text'] for f in ordered) + '\n', [f['id'] for f in ordered]
