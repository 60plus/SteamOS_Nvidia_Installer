import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CaptureIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'usr/lib/steamos-nvidia/gamescope'
        (self.base / 'bin').mkdir(parents=True)
        (self.root / 'etc').mkdir()
        (self.root / 'etc/os-release').write_text('VERSION_ID="3.8.16"\n')
        session = self.root / 'usr/lib/steamos/gamescope-session'
        session.parent.mkdir(parents=True)
        # LF on purpose: write_text would use CRLF on a Windows host and the test
        # would measure the host rather than the recipe format SteamOS ships.
        session.write_bytes(b'exec gamescope \\\n --steam\n')
        (self.base / 'bin/gamescope').write_bytes(b'test-binary')
        (self.base / 'Gamescope-LICENSE').write_text('test-license')
        (self.base / 'gamescope-build.json').write_text(json.dumps({
            'commit': '2b79e07b3da1723c7e5c5f44f18de36c6cb78b9e',
            'files': {'usr/bin/gamescope': hashlib.sha256(b'test-binary').hexdigest()}}))
        self.override = self.root / 'usr/lib/systemd/user/gamescope-session.service.d/30-nvidia-capture.conf'

    def run_install(self, version='gamescope 3.16.23.4-1', loader='0', probe='0'):
        # pc_install_gamescope asks three different questions through chroot, and a
        # test has to be able to fail one without the others: the installed package,
        # whether our libraries resolve in this root, and whether the artifact accepts
        # the session's flags. The probe call is recorded so a test can check which
        # flags were passed and that --help went last. The record is NUL delimited and
        # comes from "$@", because "$*" cannot show arguments glued into one.
        code = '''source lib/pc-support.sh
chroot() {
  case $2 in
    pacman) printf '%s\\n' "$TEST_VERSION" ;;
    /usr/lib/ld-linux-x86-64.so.2) return "$TEST_LOADER" ;;
    *) printf '%s\\0' "$@" >> "$1/probe-argv.bin"; return "$TEST_PROBE" ;;
  esac
}
pc_install_gamescope "$1"
'''
        return subprocess.run(['bash', '-c', code, 'test', str(self.root)], cwd=ROOT,
            env={**os.environ, 'TEST_VERSION': version, 'TEST_LOADER': loader,
                 'TEST_PROBE': probe}, capture_output=True, text=True)

    def probe_arguments(self):
        """The exact arguments the probe passed after our binary's path."""
        words = (self.root / 'probe-argv.bin').read_bytes().split(bytes([0]))
        words = [word.decode('utf-8') for word in words if word]
        binary = '/usr/lib/steamos-nvidia/gamescope/bin/gamescope'
        self.assertIn(binary, words)
        return words[words.index(binary) + 1:]

    def test_a_newer_release_keeps_the_correction_when_the_flags_are_accepted(self):
        """Version numbers no longer decide the selection; accepting the flags does.

        The rule used to require SteamOS 3.8 and an exact package equality, so the
        correction switched itself off on 3.9 even though the maintainer measured it
        working there on 2026-09-30 with Valve's gamescope 3.16.30-2: Game Mode
        started, menus were clean, the overlay and Remote Play worked. A test used to
        assert that stand-aside, which is why the behaviour outlived the measurement.
        """
        for release, package in (('3.8.14', 'gamescope 3.16.23.2-1'),
                                 ('3.9.1', 'gamescope 3.16.26-2'),
                                 ('3.9.2', 'gamescope 3.16.30-2')):
            with self.subTest(release=release):
                (self.root / 'etc/os-release').write_text(f'VERSION_ID="{release}"\n')
                self.assertEqual(self.run_install(package).returncode, 0)
                self.assertIn('/usr/lib/steamos-nvidia/gamescope/bin',
                              self.override.read_text())

    def test_a_flag_the_artifact_does_not_accept_stands_aside_without_failing(self):
        # The one case where standing aside is honest. It is not an error: the install
        # continues on Valve's compositor and status.txt says so.
        (self.root / 'etc/os-release').write_text('VERSION_ID="3.9.2"\n')
        result = self.run_install('gamescope 3.16.30-2', probe='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.override.exists())
        self.assertTrue((self.base / 'status.txt').read_text().startswith('stock'))

    def test_the_probe_passes_each_flag_as_its_own_argument(self):
        """Every flag arrives separately, a value with a space stays one word,
        and --help is last.

        The first version joined the tokens with NUL, which command substitution drops
        with a warning, so every flag arrived glued into a single argument. A fixture
        carrying one flag could not see that; a probe against the real binary could.
        With the real recipe's twenty-five tokens the probe would have failed for a
        reason that had nothing to do with the flags, and the correction would never
        have been selected on any machine. --help goes last because getopt stops at
        the first flag it does not know, so asking for help earlier would print usage
        and exit 0 before reaching it.
        """
        (self.root / 'usr/lib/steamos/gamescope-session').write_bytes(
            b"exec gamescope --generate-drm-mode fixed -w 1280 -O '*,eDP-1' --title 'two words' -e\n")
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(self.probe_arguments(), [
            '--generate-drm-mode', 'fixed', '-w', '1280', '-O', '*,eDP-1',
            '--title', 'two words', '-e', '--help'])

    def test_a_recipe_line_that_does_not_parse_is_refused_rather_than_guessed(self):
        # An unbalanced quote cannot be split into flags at all. Standing aside is the
        # answer; inventing a flag list is not.
        (self.root / 'usr/lib/steamos/gamescope-session').write_bytes(
            b"exec gamescope --title 'unbalanced\n")
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse(self.override.exists())

    def test_a_recipe_with_two_exec_lines_is_not_guessed_at(self):
        (self.root / 'usr/lib/steamos/gamescope-session').write_bytes(
            b'exec gamescope --steam\nexec gamescope --other\n')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse(self.override.exists())

    def test_only_the_flags_before_a_child_separator_are_probed(self):
        # Everything after a bare -- belongs to the child, so appending --help there
        # would test the child instead of our binary.
        (self.root / 'usr/lib/steamos/gamescope-session').write_bytes(
            b'exec gamescope --steam -- /usr/bin/steam-runtime --silent\n')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(self.probe_arguments(), ['--steam', '--help'])

    def set_artifact_commit(self, commit):
        data = json.loads((self.base / 'gamescope-build.json').read_text())
        data['commit'] = commit
        (self.base / 'gamescope-build.json').write_text(json.dumps(data))

    def test_a_later_point_release_keeps_the_correction(self):
        """The selection follows the Gamescope package, not a SteamOS point release.

        Valve moved stable from 3.8.16 to 3.8.28 on 22 September 2026. The rule used
        to name 3.8.16, so the correction switched itself off on an ordinary system
        update and Remote Play from the machine went back to a black picture, which
        the maintainer hit on 2026-09-25.
        """
        self.set_artifact_commit('154f435a2c0026510545b7b7524d104bed253cb3')
        for release in ['3.8.28', '3.8.16', '3.8.99']:
            with self.subTest(release=release):
                (self.root / 'etc/os-release').write_text(f'VERSION_ID="{release}"\n')
                self.assertEqual(self.run_install('gamescope 3.16.23.6-1').returncode, 0)
                self.assertIn('/usr/lib/steamos-nvidia/gamescope/bin', self.override.read_text())

    def test_an_artifact_built_against_another_package_is_still_carried(self):
        # It used to be refused for not matching the installed package. That rule was
        # precautionary and the measurement went the other way, so the only question
        # left is whether this binary accepts the flags this session will pass it.
        (self.root / 'etc/os-release').write_text('VERSION_ID="3.8.28"\n')
        self.assertEqual(self.run_install('gamescope 3.16.23.6-1').returncode, 0)
        self.assertIn('/usr/lib/steamos-nvidia/gamescope/bin', self.override.read_text())

    def test_an_unknown_artifact_is_refused_rather_than_trusted(self):
        self.set_artifact_commit('0' * 40)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsupported Gamescope capture artifact', result.stderr)
        self.assertFalse(self.override.exists())

    def test_corruption_and_incompatible_libraries_cannot_activate(self):
        self.assertNotEqual(self.run_install(loader='1').returncode, 0)
        self.assertFalse(self.override.exists())
        (self.base / 'bin/gamescope').write_bytes(b'corrupt')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertFalse(self.override.exists())

    def test_a_newer_package_is_kept_but_a_recipe_we_cannot_select_in_is_not(self):
        self.assertEqual(self.run_install('gamescope 3.16.23.4-2').returncode, 0)
        self.assertIn('/usr/lib/steamos-nvidia/gamescope/bin', self.override.read_text())
        # An absolute path in the recipe cannot be redirected by PATH at all, so there
        # is nothing honest to select and the correction stays off.
        (self.root / 'usr/lib/steamos/gamescope-session').write_bytes(b'exec /usr/bin/gamescope\n')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse(self.override.exists())

    def test_no_artifact_is_noop(self):
        shutil.rmtree(self.base)
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse(self.override.exists())
    def test_manifest_survives_capture_activation_and_fallback(self):
        import re
        source = (ROOT / 'lib/pc-support.sh').read_text()
        block = source.split('pc_write_addon_manifest() {', 1)[1].split('if [[', 1)[0]
        for rel in re.findall(r'(?m)^    (\S+)', block):
            rel = rel.rstrip(')')
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('fixture')
        (self.root / 'etc/os-release').write_text('VERSION_ID="3.8.14"\n')
        self.assertEqual(self.run_install('gamescope 3.16.23.2-1').returncode, 0)
        def manifest(command):
            return subprocess.run(['bash', '-c',
                'source lib/pc-support.sh; ' + command, 'test', str(self.root)],
                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(manifest('pc_write_addon_manifest "$1"').returncode, 0)
        check = 'cd "$1" && sha256sum --check usr/lib/steamos-nvidia/addons.sha256'
        (self.root / 'etc/os-release').write_text('VERSION_ID="3.8.16"\n')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(manifest(check).returncode, 0)
        self.assertEqual(manifest('pc_write_addon_manifest "$1"').returncode, 0)
        (self.root / 'etc/os-release').write_text('VERSION_ID="3.9.1"\n')
        self.assertEqual(self.run_install('gamescope 3.16.26-2').returncode, 0)
        self.assertEqual(manifest(check).returncode, 0)
        (self.base / 'bin/gamescope').write_bytes(b'corrupt')
        self.assertNotEqual(manifest(check).returncode, 0)
