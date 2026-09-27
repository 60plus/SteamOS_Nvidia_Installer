import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('manager', Path(__file__).resolve().parents[1] / 'scripts/driver-manager.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ManagerTests(unittest.TestCase):
    def test_only_complete_sets_sorted_numerically(self):
        indexes = {
            'nvidia-utils': 'nvidia-utils-610.9.0-2-x86_64.pkg.tar.zst nvidia-utils-610.10.0-1-x86_64.pkg.tar.zst nvidia-utils-611.0.0-1-x86_64.pkg.tar.zst',
            'nvidia-open-dkms': 'nvidia-open-dkms-610.9.0-1-x86_64.pkg.tar.zst nvidia-open-dkms-610.10.0-2-x86_64.pkg.tar.zst',
            'lib32-nvidia-utils': 'lib32-nvidia-utils-610.9.0-1-x86_64.pkg.tar.zst lib32-nvidia-utils-610.10.0-1-x86_64.pkg.tar.zst'}
        self.assertEqual(m.versions(indexes), ['610.10.0-1', '610.9.0-2'])

    def test_failed_operation_never_offers_reboot(self):
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run, patch.object(m, 'dialog') as ui:
            self.assertEqual(m.worker('install', '610.43.03-5'), 1)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(ui.call_args.args[0], '--error')

    def test_later_preserves_running_session(self):
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run, patch.object(m, 'dialog', return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(m.worker('rollback', ''), 0)
            self.assertEqual(run.call_count, 1)
            self.assertIn('--wait', run.call_args.args[0])

    def test_invalid_version_never_executes(self):
        with patch.object(m.subprocess, 'run') as run:
            with self.assertRaises(ValueError): m.worker('install', '--help')
            run.assert_not_called()

    def test_list_omits_unsupported_no_wrap(self):
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            m.dialog('--list', 'Choose', '--column', 'Action', 'Test')
            self.assertNotIn('--no-wrap', run.call_args.args[0])

    def test_dialog_error_is_not_cancel(self):
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 255, '', 'unsupported option')):
            with self.assertRaisesRegex(RuntimeError, 'unsupported option'):
                m.dialog('--list', 'Choose')


class CompatibilityTests(unittest.TestCase):
    def page(self):
        return '<h3>Current NVIDIA GPUs</h3><table><tr><td>NVIDIA GeForce GTX 1650</td><td>1F82</td></tr><tr><td>NVIDIA GeForce RTX 5060</td><td>2D05</td></tr><tr><td>NVIDIA GeForce GTX 1080</td><td>1B80</td></tr><tr><td>NVIDIA GeForce RTX 4060 Laptop GPU</td><td>28A0 1028 1234</td></tr></table><h3>Legacy GPUs</h3><table><tr><td>NVIDIA GeForce RTX 9999</td><td>FFFF</td></tr></table>'

    def test_only_current_open_module_geforce_families(self):
        self.assertEqual(m.gpu_summary(self.page(), [('2D05', '1043', '0001')]), 'GTX 16, RTX 40, RTX 50')
        self.assertIsNone(m.gpu_summary(self.page(), [('1B80', '1043', '0001')]))
        self.assertIsNone(m.gpu_summary(self.page(), [('FFFF', '1043', '0001')]))

    def test_subsystem_specific_and_multi_gpu_matches(self):
        self.assertIsNotNone(m.gpu_summary(self.page(), [('28A0', '1028', '1234')]))
        self.assertIsNone(m.gpu_summary(self.page(), [('28A0', '1028', '9999')]))
        self.assertIsNone(m.gpu_summary(self.page(), [('2D05', '1043', '0001'), ('FFFF', '1043', '0001')]))

    def test_missing_or_failed_metadata_never_assumes_support(self):
        for fetch in [lambda v: 'invalid page', lambda v: '<h3>Current NVIDIA GPUs</h3><table></table>']:
            self.assertEqual(m.compatible_versions(['610.43.03-5'], [('2D05', '1043', '0001')], fetch), [])

    def test_package_revisions_share_one_support_lookup(self):
        calls = []
        def fetch(v):
            calls.append(v)
            return self.page()
        result = m.compatible_versions(['610.43.03-5', '610.43.03-4'], [('2D05', '1043', '0001')], fetch)
        self.assertEqual(len(result), 2)
        self.assertEqual(calls, ['610.43.03'])


class ProjectTestedDriversAreNotJustNvidiaMatches(unittest.TestCase):
    """The chooser offers ten driver versions and used to mark them all the same.

    NVIDIA documenting a GPU in a driver's range says nothing about whether this
    project ever booted that driver, and the green marker read as if it did. The
    tested set lives in this script because the script travels in the signed bundle
    and reaches installed systems, while config/build-baselines.json is a build input
    that never leaves the workshop, so a test has to hold the two in step.
    """

    def baseline(self):
        path = Path(__file__).resolve().parents[1] / 'config/build-baselines.json'
        return json.loads(path.read_text(encoding='utf-8'))['tested_driver']

    def test_the_tested_set_matches_the_build_baseline(self):
        self.assertIn(self.baseline(), m.TESTED_DRIVERS,
                      'the driver the image is built with has to be marked as tested')
        for version in m.TESTED_DRIVERS:
            with self.subTest(version=version):
                self.assertRegex(version, r'^[0-9]+(?:\.[0-9]+)+-[0-9]+(?:\.[0-9]+)*$')

    def test_a_tested_and_an_untested_version_do_not_look_alike(self):
        tested = self.baseline()
        rows, note = m.chooser_rows([(tested, 'RTX 50'), ('999.99.99-1', 'RTX 50')])
        self.assertEqual(6, len(rows))
        self.assertIn('tested by this project', rows[2])
        self.assertIn('untested here', rows[5])
        self.assertNotEqual(rows[2], rows[5], 'the two claims must not share a marker')
        self.assertIn(tested, note)

    def test_when_nothing_offered_was_tested_the_note_says_so(self):
        rows, note = m.chooser_rows([('999.99.99-1', 'RTX 50'), ('999.99.98-1', 'RTX 50')])
        self.assertIn('untested here', rows[2])
        self.assertIn('untested here', rows[5])
        self.assertIn('None of the versions offered here', note)
        self.assertIn(self.baseline(), note, 'the note has to name what was tested instead')

    def test_the_note_never_claims_a_version_that_is_not_offered(self):
        _, note = m.chooser_rows([(self.baseline(), 'RTX 50')])
        self.assertNotIn('None of the versions', note)
