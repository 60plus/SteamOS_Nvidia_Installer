import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import socket
import stat
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'scripts/steamos-nvidia-diagnostics').read_text(encoding='utf-8')
PROBE = SCRIPT.split("<<'SOURCE_SUMMARY'\n", 1)[1].split('\nSOURCE_SUMMARY\n', 1)[0]
OFFICIAL = json.loads((ROOT / 'config/github-stable.json').read_text())
# fcntl is only used by the updater's installation path, never by its validator.
with patch.dict(sys.modules, {'fcntl': types.ModuleType('fcntl')}) if os.name == 'nt' else contextlib.nullcontext():
    UPDATER = runpy.run_path(str(ROOT / 'scripts/installer-update.py'))


class SourceSummary(unittest.TestCase):
    def report(self, config=None, raw=None, error=None, updater_error=None,
               uid=0, mode=stat.S_IFREG | 0o644, metadata_error=None):
        data = raw if raw is not None else json.dumps(OFFICIAL if config is None else config).encode()
        output = io.StringIO()
        with patch.object(Path, 'open', side_effect=error, return_value=io.BytesIO(data)) as opened, \
                patch.object(Path, 'lstat', side_effect=metadata_error,
                             return_value=types.SimpleNamespace(st_uid=uid, st_mode=mode)), \
                patch.object(runpy, 'run_path', side_effect=updater_error, return_value=UPDATER), \
                patch.object(socket, 'socket', side_effect=AssertionError('Network access')), \
                contextlib.redirect_stdout(output):
            exec(compile(PROBE, '<diagnostic source probe>', 'exec'), {})
        if metadata_error or stat.S_ISLNK(mode) or uid != 0 or mode & 0o022:
            opened.assert_not_called()
        else:
            opened.assert_called_once_with('rb')
        return output.getvalue()

    def test_official_source_and_channel(self):
        result = self.report()
        self.assertIn('Endpoint: official GitHub repository 60plus/SteamOS_Nvidia_Installer', result)
        self.assertIn('Prereleases: disabled', result)
        self.assertIn('signing key and connectivity not checked', result)
        self.assertNotIn(OFFICIAL['public_key'], result)

    def test_custom_source_prints_servers_but_not_names_paths_or_keys(self):
        cfg = dict(OFFICIAL, name='SECRET_NAME', public_key='-----BEGIN PUBLIC KEY-----SECRET_KEY',
                   release_api='https://updates.example:8443/api/SECRET_PATH/releases/',
                   download_origin='https://downloads.example:9443', allow_prerelease=True)
        result = self.report(cfg)
        self.assertIn('Endpoint: custom', result)
        self.assertIn('Release server: https://updates.example:8443 (path omitted)', result)
        self.assertIn('Download server: https://downloads.example:9443', result)
        self.assertIn('Prereleases: enabled', result)
        self.assertNotIn('SECRET', result)

    def test_official_api_with_custom_download_server_is_custom(self):
        result = self.report(dict(OFFICIAL, download_origin='https://mirror.example'))
        self.assertIn('Endpoint: custom', result)

    def test_legacy_official_source_is_identified(self):
        result = self.report(UPDATER['LEGACY_SOURCE'])
        self.assertIn('Endpoint: legacy official GitHub repository 60plus/steamos-nvidia-installer', result)
        self.assertNotIn('Endpoint: custom', result)
        self.assertNotIn(UPDATER['LEGACY_SOURCE']['public_key'], result)

    def test_updater_rejected_permissions_are_reported_without_reading_config(self):
        for uid, mode in [(1000, stat.S_IFREG | 0o644), (0, stat.S_IFREG | 0o664),
                          (0, stat.S_IFREG | 0o646), (0, stat.S_IFLNK | 0o777)]:
            with self.subTest(uid=uid, mode=mode):
                self.assertEqual(self.report(uid=uid, mode=mode),
                    'Configuration: rejected by updater (symlink, not root-owned, or writable by others)\n')

    def test_metadata_errors_are_reported_without_reading_config(self):
        for error, state in [(FileNotFoundError('SECRET'), 'missing'), (PermissionError('SECRET'), 'unreadable')]:
            with self.subTest(state=state):
                self.assertEqual(self.report(metadata_error=error), 'Configuration: ' + state + '\n')

    def test_missing_and_unreadable_are_distinct_without_exception_details(self):
        for error, expected in [(FileNotFoundError('SECRET_PATH'), 'missing'),
                                (PermissionError('SECRET_PATH'), 'unreadable'),
                                (IsADirectoryError('SECRET_PATH'), 'unreadable')]:
            with self.subTest(expected=expected):
                self.assertEqual(self.report(error=error), 'Configuration: ' + expected + '\n')

    def test_invalid_json_and_encoding_do_not_escape_or_expose_content(self):
        for raw in [b'{SECRET', b'\xffSECRET', b'[]', b'null', b'{}',
                    b'[' * 2000 + b']' * 2000, b' ' * 65537]:
            with self.subTest(raw=raw[:15]):
                self.assertEqual(self.report(raw=raw), 'Configuration: invalid\n')

    def test_invalid_fields_do_not_escape_or_expose_values(self):
        for field, value in [('release_api', None),
                             ('download_origin', []), ('allow_prerelease', 'SECRET'),
                             ('public_key', 'SECRET')]:
            with self.subTest(field=field):
                self.assertEqual(self.report(dict(OFFICIAL, **{field: value})), 'Configuration: invalid\n')

    def test_display_name_is_not_printed_or_subject_to_another_schema(self):
        result = self.report(dict(OFFICIAL, name={'SECRET': True}))
        self.assertIn('Endpoint: official GitHub repository', result)
        self.assertNotIn('SECRET', result)

    def test_unloadable_updater_does_not_expose_exception_or_stop_report(self):
        for error in [FileNotFoundError('SECRET_PATH'), SyntaxError('SECRET'), ImportError('SECRET')]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(self.report(updater_error=error),
                    'Configuration: present; validation unavailable (updater could not be loaded)\n')

    def test_url_credentials_queries_fragments_and_controls_are_never_printed(self):
        for field in ['release_api', 'download_origin']:
            for value in ['https://user:SECRET@updates.example/api/releases/',
                          'https://updates.example/api/releases/?token=SECRET',
                          'https://updates.example/api/releases/#SECRET',
                          'https://updates.example:99999/api/releases/',
                          'https://updates.example/\nSECRET/releases/',
                          'https://updates.example/\x1bSECRET/releases/']:
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.report(dict(OFFICIAL, **{field: value})), 'Configuration: invalid\n')


if __name__ == '__main__':
    unittest.main()
