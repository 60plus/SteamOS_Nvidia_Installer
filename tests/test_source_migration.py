import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration_updater', ROOT / 'scripts/installer-update.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


@unittest.skipUnless(os.geteuid() == 0, 'Source ownership tests require a Linux root container')
class SourceMigration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target = self.root / 'usr/lib/steamos-nvidia/installer-update-source.json'
        self.target.parent.mkdir(parents=True)
        self.write(updater.LEGACY_SOURCE)

    def write(self, cfg):
        self.target.write_text(json.dumps(cfg, indent=2) + '\n')
        self.target.chmod(0o644)

    def test_only_prepared_slot_changes_and_second_run_is_noop(self):
        active = self.root / 'active-source.json'
        original = self.target.read_bytes()
        active.write_bytes(original)
        with patch.object(updater, 'CONFIG', active):
            self.assertTrue(updater.migrate_source(self.root))
            self.assertEqual(active.read_bytes(), original)
        expected = dict(updater.LEGACY_SOURCE, release_api=updater.RELEASE_API)
        self.assertEqual(updater.source(self.target), expected)
        self.assertEqual(self.target.stat().st_uid, 0)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o644)
        after = self.target.read_bytes()
        with patch.object(updater.os, 'replace') as replace:
            self.assertFalse(updater.migrate_source(self.root))
            replace.assert_not_called()
        self.assertEqual(self.target.read_bytes(), after)

    def test_current_official_config_matches_migration_and_keeps_key(self):
        current = json.loads((ROOT / 'config/github-stable.json').read_text())
        self.assertEqual(current, dict(updater.LEGACY_SOURCE, release_api=updater.RELEASE_API))

    def test_custom_sources_are_preserved_byte_for_byte(self):
        for field, value in [
            ('release_api', 'https://api.github.com/repos/example/custom/releases/'),
            ('public_key', '-----BEGIN PUBLIC KEY-----\ncustom-key\n-----END PUBLIC KEY-----\n'),
            ('allow_prerelease', True), ('download_origin', 'https://example.invalid'),
            ('name', 'Custom installation'), ('custom_field', True),
        ]:
            with self.subTest(field=field):
                cfg = copy.deepcopy(updater.LEGACY_SOURCE)
                cfg[field] = value
                self.write(cfg)
                before = self.target.read_bytes()
                self.assertFalse(updater.migrate_source(self.root))
                self.assertEqual(self.target.read_bytes(), before)

    def test_missing_source_is_not_created(self):
        self.target.unlink()
        self.assertFalse(updater.migrate_source(self.root))
        self.assertFalse(self.target.exists())

    def test_live_root_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'prepared image'):
            updater.migrate_source('/')

    def test_symlink_destination_is_refused(self):
        other = self.root / 'original.json'
        self.target.rename(other)
        before = other.read_bytes()
        self.target.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            updater.migrate_source(self.root)
        self.assertEqual(other.read_bytes(), before)

    def test_build_workspace_can_have_a_symlinked_parent(self):
        parent = self.root / 'actual'
        prepared = parent / 'image'
        prepared.mkdir(parents=True)
        (self.root / 'usr').rename(prepared / 'usr')
        alias = self.root / 'home-alias'
        alias.symlink_to(parent, target_is_directory=True)
        self.assertTrue(updater.migrate_source(alias / 'image'))
        target = prepared / 'usr/lib/steamos-nvidia/installer-update-source.json'
        self.assertEqual(updater.source(target)['release_api'], updater.RELEASE_API)

    def test_alias_to_live_root_is_refused(self):
        alias = self.root / 'live-alias'
        alias.symlink_to('/', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'prepared image'):
            updater.migrate_source(alias)

    def test_symlink_parent_is_refused(self):
        parent = self.target.parent
        other = self.root / 'elsewhere'
        parent.rename(other)
        parent.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            updater.migrate_source(self.root)

    def test_unsafe_permissions_and_owner_are_refused(self):
        for mode in (0o666, 0o664):
            with self.subTest(mode=mode):
                self.target.chmod(mode)
                with self.assertRaisesRegex(ValueError, 'root-owned'):
                    updater.migrate_source(self.root)
        self.target.chmod(0o644)
        os.chown(self.target, 1000, 1000)
        with self.assertRaisesRegex(ValueError, 'root-owned'):
            updater.migrate_source(self.root)

    def test_bad_json_refused_without_replacing_original(self):
        self.target.write_text('{')
        with self.assertRaises(ValueError):
            updater.migrate_source(self.root)
        self.assertEqual(self.target.read_text(), '{')

    def test_invalid_destination_api_refused_before_writing(self):
        before = self.target.read_bytes()
        with patch.object(updater, 'RELEASE_API', 'http://invalid'):
            with self.assertRaises(ValueError):
                updater.migrate_source(self.root)
        self.assertEqual(self.target.read_bytes(), before)

    def test_failed_atomic_replace_leaves_original_and_no_temp_file(self):
        before = self.target.read_bytes()
        with patch.object(updater.os, 'replace', side_effect=OSError('injected failure')):
            with self.assertRaises(OSError):
                updater.migrate_source(self.root)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(list(self.target.parent.glob('.installer-update-source-*')), [])

    def test_existing_install_hook_migrates_source_and_records_checksum(self):
        # Older signed updaters already call this shell function from the NEW payload.
        # Exercise that contract instead of calling the migration helper directly.
        (self.target.parent / 'installer-update.py').write_bytes((ROOT / 'scripts/installer-update.py').read_bytes())
        (self.root / 'usr/bin').mkdir(parents=True)
        for name in (
            'usr/lib/steamos-nvidia/hdr-defaults.py',
            'usr/lib/steamos-nvidia/safe-graphics.py',
            'usr/lib/steamos-nvidia/bluetooth-resume.py',
            'usr/lib/steamos-nvidia/install-target.py',
            'usr/bin/steamos-nvidia-diagnostics',
            'usr/lib/systemd/user/steam-launcher.service.d/10-nvidia-hdr-default.conf',
            'usr/lib/systemd/user/gamescope-session.service.d/20-nvidia-safe-graphics.conf',
            'usr/lib/systemd/user/steamos-nvidia-bluetooth-resume.service',
            'usr/share/applications/steamos-nvidia-safe-graphics.desktop',
            'usr/share/applications/steamos-nvidia-normal-graphics.desktop',
            'usr/lib/steamos-nvidia/installer-update-ui.py',
            'usr/lib/steamos-nvidia/installer-update.png',
            'usr/lib/steamos-nvidia/integration-version.json',
        ):
            fixture = self.root / name
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text('fixture\n')
        subprocess.run(['bash', '-c',
                        'set -e; source "$1"; pc_install_installer_update "$2"; pc_write_addon_manifest "$2"',
                        'migration-test', str(ROOT / 'lib/pc-support.sh'), str(self.root)], check=True)
        self.assertEqual(updater.source(self.target)['release_api'], updater.RELEASE_API)
        checksum = self.target.parent / 'addons.sha256'
        self.assertTrue(checksum.is_file())
        subprocess.run(['sha256sum', '--quiet', '-c', str(checksum)], cwd=self.root, check=True)
