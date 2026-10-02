"""Repository-owned prose should remain English; personal data is excluded."""
from pathlib import Path
import re
import unittest


class LanguageTests(unittest.TestCase):
    def test_source_and_docs_have_no_chinese_text(self):
        root = Path(__file__).resolve().parents[1]
        paths = [root / 'README.md', root / 'WORKFLOW.md', root / 'app.py',
                 *root.glob('job_assistant/*.py'), *root.glob('tests/*.py')]
        for path in paths:
            self.assertIsNone(re.search(r'[\u3400-\u9fff]', path.read_text(encoding='utf-8-sig')), str(path))
