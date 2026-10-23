import hashlib
import importlib.util
from pathlib import Path
import tempfile
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('notifications', Path(__file__).resolve().parents[1] / 'scripts/notification-renderer.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


class Notifications(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'steamui').mkdir()
        self.state = self.root / 'state'
        self.state.mkdir()
        self.target = self.root / 'steamui' / n.ASSET
        self.original = b'prefix;' + n.BEFORE + b';suffix'
        self.target.write_bytes(self.original)
        self.guard = patch.object(n, 'ORIGINAL_SHA256', hashlib.sha256(self.original).hexdigest())
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def run_action(self, action):
        return n.update(self.root, self.state, action)

    def test_roundtrip_and_idempotence(self):
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        patched = self.target.read_bytes()
        self.assertIn(n.AFTER, patched)
        self.assertEqual(len(patched), len(self.original))
        self.assertEqual(self.run_action('apply'), 'already patched')
        self.assertEqual(self.target.read_bytes(), patched)
        self.assertEqual(self.run_action('restore'), 'restored original renderer')
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_unknown_client_with_same_snippet_is_not_modified(self):
        self.target.write_bytes(self.original + b'new Steam version')
        for action in ['apply', 'restore']:
            self.assertIn('unsupported', self.run_action(action))
        self.assertEqual(list(self.state.iterdir()), [])

    def test_corrupt_backup_prevents_restore(self):
        self.run_action('apply')
        next(self.state.iterdir()).write_bytes(b'bad backup')
        before = self.target.read_bytes()
        with self.assertRaises(ValueError):
            self.run_action('restore')
        self.assertEqual(before, self.target.read_bytes())

    def test_updated_file_never_restored_from_old_backup(self):
        self.run_action('apply')
        self.target.write_bytes(b'new client')
        self.assertIn('unsupported', self.run_action('restore'))
        self.assertEqual(self.target.read_bytes(), b'new client')

    def test_symlink_rejected(self):
        self.target.unlink()
        other = self.root / 'other'
        other.write_bytes(self.original)
        self.target.symlink_to(other)
        with self.assertRaises(OSError):
            self.run_action('apply')
        self.assertEqual(other.read_bytes(), self.original)

    def test_startup_applies_and_reloads_once(self):
        with patch.object(n, 'browser_processes', return_value=[42]), \
                patch.object(n.os, 'pidfd_open', return_value=99), \
                patch.object(n.os, 'close') as close, \
                patch.object(n.time, 'sleep'), \
                patch.object(n.signal, 'pidfd_send_signal') as kill:
            self.assertIn('reloaded', n.startup(self.root, self.state))
            kill.assert_called_once_with(99, n.signal.SIGTERM)
            close.assert_called_once_with(99)

    def test_startup_unknown_asset_never_restarts_browser(self):
        self.target.write_bytes(b'unknown client')
        with patch.object(n, 'browser_processes', return_value=[42]), \
                patch.object(n.os, 'pidfd_open', return_value=99), \
                patch.object(n.os, 'close'), patch.object(n.time, 'sleep'), \
                patch.object(n.signal, 'pidfd_send_signal') as kill:
            self.assertIn('unsupported', n.startup(self.root, self.state))
            kill.assert_not_called()

    def test_disabled_startup_does_not_touch_browser(self):
        (self.state / 'disabled').touch()
        with patch.object(n, 'browser_processes') as processes:
            self.assertIn('disabled', n.startup(self.root, self.state))
            processes.assert_not_called()

    def test_legacy_patch_migrates_without_losing_original(self):
        self.target.write_bytes(self.original.replace(n.BEFORE, n.LEGACY_AFTER))
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(len(self.target.read_bytes()), len(self.original))
        self.run_action('restore')
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_status_does_not_write(self):
        self.assertEqual(self.run_action('status'), 'original renderer on disk')
        self.assertEqual(list(self.state.iterdir()), [])

    def new_client(self):
        target = self.root / 'steamui' / n.SP_ASSET
        original = b'prefix;' + n.SP_BEFORE + b';suffix'
        target.write_bytes(original)
        guard = patch.object(n, 'SP_ORIGINAL_SHA256', hashlib.sha256(original).hexdigest())
        guard.start()
        self.addCleanup(guard.stop)
        return target, original

    def test_new_client_roundtrip_with_stale_chunk(self):
        target, original = self.new_client()
        self.target.write_bytes(b'obsolete client chunk')
        self.assertEqual(self.run_action('status'), 'original renderer on disk')
        self.assertEqual(list(self.state.iterdir()), [])
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(target.read_bytes(), original.replace(n.SP_BEFORE, n.SP_AFTER))
        self.assertEqual(len(target.read_bytes()), len(original))
        self.assertEqual(self.run_action('apply'), 'already patched')
        self.assertEqual(self.run_action('status'), 'embedded renderer active on disk')
        self.assertEqual(self.run_action('restore'), 'restored original renderer')
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.target.read_bytes(), b'obsolete client chunk')

    def test_new_client_without_old_chunk(self):
        target, original = self.new_client()
        self.target.unlink()
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(target.read_bytes(), original.replace(n.SP_BEFORE, n.SP_AFTER))

    def test_new_client_does_not_patch_recognized_but_obsolete_chunk(self):
        target, original = self.new_client()
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(target.read_bytes(), original.replace(n.SP_BEFORE, n.SP_AFTER))

    def test_unknown_new_client_never_falls_back_to_recognized_old_chunk(self):
        target, original = self.new_client()
        changed = original + b'new Steam version'
        target.write_bytes(changed)
        for action in ['status', 'apply', 'restore']:
            self.assertIn('unsupported', self.run_action(action))
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_new_client_update_never_restored_from_old_backup(self):
        target, original = self.new_client()
        self.run_action('apply')
        changed = original + b'new Steam version'
        target.write_bytes(changed)
        self.assertIn('unsupported', self.run_action('restore'))
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_old_client_with_small_sp_entry_point(self):
        (self.root / 'steamui' / n.SP_ASSET).write_bytes(b'loadLegacyChunk();')
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(self.target.read_bytes(), self.original.replace(n.BEFORE, n.AFTER))

    def test_new_client_symlink_rejected(self):
        target, original = self.new_client()
        target.unlink()
        other = self.root / 'new-client'
        other.write_bytes(original)
        target.symlink_to(other)
        with self.assertRaises(OSError):
            self.run_action('apply')
        self.assertEqual(other.read_bytes(), original)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_new_client_startup_reloads_once(self):
        self.new_client()
        with patch.object(n, 'browser_processes', return_value=[42]), \
                patch.object(n.os, 'pidfd_open', return_value=99), \
                patch.object(n.os, 'close'), patch.object(n.time, 'sleep'), \
                patch.object(n.signal, 'pidfd_send_signal') as kill:
            self.assertIn('reloaded', n.startup(self.root, self.state))
            self.assertEqual(n.startup(self.root, self.state), 'already patched')
            kill.assert_called_once_with(99, n.signal.SIGTERM)

    def test_october_21_profile_preserves_size_and_restores_exactly(self):
        target = self.root / 'steamui' / n.SP_ASSET
        original = b'new-build;' + n.SP_BEFORE + b';different-suffix'
        target.write_bytes(original)
        with patch.object(n, 'SP_OCT21_SHA256', hashlib.sha256(original).hexdigest()):
            self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
            self.assertEqual(len(target.read_bytes()), len(original))
            self.assertEqual(self.run_action('apply'), 'already patched')
            self.assertEqual(self.run_action('restore'), 'restored original renderer')
        self.assertEqual(target.read_bytes(), original)

    def test_startup_waits_for_slow_client_update_and_reloads_once(self):
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        def browser():
            return [42] if clock[0] >= 218 else []
        with patch.object(n.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(n.time, 'sleep', side_effect=sleep), \
                patch.object(n, 'browser_processes', side_effect=browser), \
                patch.object(n.os, 'pidfd_open', return_value=99), \
                patch.object(n.os, 'close'), \
                patch.object(n.signal, 'pidfd_send_signal') as kill:
            self.assertIn('reloaded', n.startup(self.root, self.state))
            self.assertEqual(n.startup(self.root, self.state), 'already patched')
            kill.assert_called_once_with(99, n.signal.SIGTERM)

    def test_startup_deadline_with_no_browser_leaves_files_untouched(self):
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(n.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(n.time, 'sleep', side_effect=sleep), \
                patch.object(n, 'browser_processes', return_value=[]), \
                patch.object(n.os, 'pidfd_open') as pidfd:
            result = n.startup(self.root, self.state)
            self.assertIn(f'{n.STARTUP_WAIT_SECONDS} seconds', result)
            self.assertEqual(clock[0], n.STARTUP_WAIT_SECONDS)
            pidfd.assert_not_called()
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_disabling_during_startup_wait_stops_without_modifying_asset(self):
        def disable(seconds):
            (self.state / 'disabled').touch()
        with patch.object(n.time, 'sleep', side_effect=disable), \
                patch.object(n, 'browser_processes', return_value=[]):
            self.assertIn('disabled', n.startup(self.root, self.state))
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual([p.name for p in self.state.iterdir()], ['disabled'])

    def test_sigterm_interrupts_real_wait_without_touching_files(self):
        # A separate Linux process proves the extended wait is interruptible;
        # neither the real Steam browser nor the live user's files are involved.
        code = '''import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('worker',sys.argv[1])
worker=importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
def browser():
    print('waiting',flush=True)
    return []
worker.browser_processes=browser
worker.startup(Path(sys.argv[2]),Path(sys.argv[3]))
'''
        proc = subprocess.Popen([sys.executable, '-u', '-c', code, n.__file__,
                                 str(self.root), str(self.state)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        try:
            import select
            self.assertTrue(select.select([proc.stdout], [], [], 5)[0])
            self.assertEqual(proc.stdout.readline().strip(), 'waiting')
            started = time.monotonic()
            proc.terminate()
            proc.communicate(timeout=3)
            self.assertEqual(proc.returncode, -signal.SIGTERM)
            self.assertLess(time.monotonic() - started, 3)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(list(self.state.iterdir()), [])


    def test_previous_beta_profile_roundtrip(self):
        before = b've=Tt&&Lt,ht=(0,Ce.wv)();return Wt?.IsVRGamepadUIOverlayWindow()'
        after = b've=Tt&&Lt,ht=!0         ;return Wt?.IsVRGamepadUIOverlayWindow()'
        original = b'previous beta;' + before + b';end'
        self.target.write_bytes(original)
        real_digest = n.digest
        expected = '1da08ac81e2ad5c56e868bc7b18cd940d0e990a142fa26bc2445dd9ec7813c98'
        # Synthetic fixture for the retained Beta profile, without distributing
        # Valve's client asset. Production still verifies the complete file.
        with patch.object(n, 'digest', side_effect=lambda data:
                          expected if data == original else real_digest(data)):
            self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
            self.assertEqual(self.target.read_bytes(), original.replace(before, after))
            self.assertEqual(len(self.target.read_bytes()), len(original))
            self.assertEqual(self.run_action('apply'), 'already patched')
            self.assertEqual(self.run_action('restore'), 'restored original renderer')
            self.assertEqual(self.target.read_bytes(), original)

    def test_previously_patched_old_client_is_kept_without_browser_reload(self):
        self.target.write_bytes(self.original.replace(n.BEFORE, n.AFTER))
        (self.state / (n.digest(self.original) + '.original')).write_bytes(self.original)
        with patch.object(n, 'browser_processes', return_value=[42]), \
                patch.object(n.os, 'pidfd_open', return_value=99), \
                patch.object(n.os, 'close'), patch.object(n.time, 'sleep'), \
                patch.object(n.signal, 'pidfd_send_signal') as kill:
            self.assertEqual(n.startup(self.root, self.state), 'already patched')
            kill.assert_not_called()
        self.assertEqual(self.run_action('restore'), 'restored original renderer')
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_old_to_new_client_and_back_retains_separate_backups(self):
        self.run_action('apply')
        old_patched = self.target.read_bytes()
        target, original = self.new_client()
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(self.target.read_bytes(), old_patched)
        self.assertEqual(self.run_action('restore'), 'restored original renderer')
        self.assertEqual(target.read_bytes(), original)
        # A client rollback restores the old entry point and original chunk.
        target.write_bytes(b'loadLegacyChunk();')
        self.target.write_bytes(self.original)
        self.assertEqual(self.run_action('apply'), 'selected embedded renderer')
        self.assertEqual(self.target.read_bytes(), old_patched)
        self.assertEqual(self.run_action('restore'), 'restored original renderer')
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(len(list(self.state.glob('*.original'))), 2)


if __name__ == '__main__':
    unittest.main()
