import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('update_ui', Path(__file__).parents[1] / 'scripts/installer-update-ui.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class UpdateUI(unittest.TestCase):
    def test_current_release_does_not_offer_install(self):
        release = dict(installed='0.1.1', version='0.1.1')
        with patch.object(m.sys, 'argv', ['update-ui']), \
                patch.object(m.Path, 'read_text', side_effect=['VERSION_ID=3.8.16', json.dumps({'name':'GitHub'})]), \
                patch.object(m, 'dialog', return_value=SimpleNamespace(returncode=0, stdout='Check for updates')) as dialog, \
                patch.object(m.subprocess, 'Popen', return_value=MagicMock()), \
                patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(release))), \
                patch.object(m.subprocess, 'call') as launch:
            self.assertEqual(m.main(), 0)
            self.assertEqual(dialog.call_args.args[0], '--info')
            self.assertIn('up to date', dialog.call_args.args[1])
            launch.assert_not_called()
    def test_a_machine_ahead_of_its_source_is_not_offered_a_downgrade(self):
        # Equality alone said "these differ, offer the older one". A machine that took a
        # prerelease, or any machine while the next release is being prepared, met that.
        release = dict(installed='0.2.1', version='0.2.0', offer='none')
        with patch.object(m.sys, 'argv', ['update-ui']), \
                patch.object(m.Path, 'read_text', side_effect=['VERSION_ID=3.8.16', json.dumps({'name':'GitHub'})]), \
                patch.object(m, 'dialog', return_value=SimpleNamespace(returncode=0, stdout='Check for updates')) as dialog, \
                patch.object(m.subprocess, 'Popen', return_value=MagicMock()), \
                patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(release))), \
                patch.object(m.subprocess, 'call') as launch:
            self.assertEqual(m.main(), 0)
            self.assertEqual(dialog.call_args.args[0], '--info')
            self.assertIn('up to date', dialog.call_args.args[1])
            self.assertIn('0.2.1', dialog.call_args.args[1])
            launch.assert_not_called()

    def test_a_repair_is_offered_and_names_the_files_that_are_missing(self):
        release = dict(installed='0.2.0', version='0.2.0', offer='repair',
                       missing=['Gamescope-LICENSE', 'gamescope', 'gamescope-build.json'],
                       source='GitHub', notes='Deliver the corrected Gamescope build',
                       tag='v0.2.0', manifest_sha256='0' * 64)
        with patch.object(m.sys, 'argv', ['update-ui']), \
                patch.object(m.Path, 'read_text', side_effect=['VERSION_ID=3.8.16', json.dumps({'name':'GitHub'})]), \
                patch.object(m, 'dialog', return_value=SimpleNamespace(returncode=0, stdout='Check for updates')) as dialog, \
                patch.object(m.subprocess, 'Popen', return_value=MagicMock()), \
                patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(release))), \
                patch.object(m.subprocess, 'call', return_value=0) as launch:
            self.assertEqual(m.main(), 0)
            self.assertEqual(dialog.call_args.args[0], '--question')
            text = dialog.call_args.args[1]
            self.assertIn('already installed', text)
            for name in release['missing']:
                self.assertIn(name, text)
            self.assertEqual(launch.call_args.args[0][-3:], ['install', 'v0.2.0', '0' * 64])

    def test_a_check_too_old_to_decide_still_behaves_as_before(self):
        # The window and the tool are updated in the same transaction, but a rollback can
        # leave an older check answering a newer window.
        release = dict(installed='0.1.1', version='0.1.1')
        with patch.object(m.sys, 'argv', ['update-ui']), \
                patch.object(m.Path, 'read_text', side_effect=['VERSION_ID=3.8.16', json.dumps({'name':'GitHub'})]), \
                patch.object(m, 'dialog', return_value=SimpleNamespace(returncode=0, stdout='Check for updates')) as dialog, \
                patch.object(m.subprocess, 'Popen', return_value=MagicMock()), \
                patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(release))), \
                patch.object(m.subprocess, 'call') as launch:
            self.assertEqual(m.main(), 0)
            self.assertEqual(dialog.call_args.args[0], '--info')
            launch.assert_not_called()
