import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SourceLineEndings(unittest.TestCase):
    def test_linux_builder_inputs_have_lf(self):
        paths = [ROOT / 'VERSION', *sorted((ROOT / 'patches').rglob('*.patch'))]
        self.assertGreater(len(paths), 1)
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                data = path.read_bytes()
                self.assertNotIn(b'\r', data)
                self.assertTrue(data.endswith(b'\n'))

    def test_every_documented_page_has_lf(self):
        """A Markdown file that arrives with CRLF poisons the next edit of it.

        Nothing enforced this and two files drifted: one build report was
        converted by hand on a mistaken measurement, and docs/PLAN-0.1.8.md was
        written whole by a script on Windows. Reading such a file and writing it
        back doubles every ending, so the damage spreads to whoever edits next.
        `.gitattributes` now normalises `*.md`, and this test is the loud part.

        A trailing newline is deliberately not asserted here. These pages include
        planning notes that are edited by hand between commits, and a missing last
        newline costs nothing, while a stray carriage return spreads.
        """
        pages = [*sorted(ROOT.glob('*.md')), *sorted((ROOT / 'docs').rglob('*.md'))]
        # The published repository carries the manual and not this project's working
        # notes, so it has far fewer pages than the workshop. The bound only has to
        # prove the glob found something in either tree.
        self.assertGreater(len(pages), 10, 'the glob has to actually find the documentation')
        for path in pages:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn(b'\r', path.read_bytes())
