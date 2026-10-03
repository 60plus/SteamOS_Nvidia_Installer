import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer_update', Path(__file__).parents[1] / 'scripts/installer-update.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def manifest():
    return dict(format=1, version='0.1.0-dev.1', steamos=['3.8.16'], notes='Update tools',
                bundle_sha256='0'*64, files={name: m.digest(b'test') for name in m.FILES})


class TheConfirmationWindowStaysOnTheScreen(unittest.TestCase):
    """Zenity grows a dialog to fit its text and ignores --height.

    Measured on 2026-09-26 with the 0.1.6 release notes, 94 lines and 6343
    characters: the confirmation window grew past the bottom of a 1440p screen
    and neither Continue nor Cancel could be clicked, so the update could not be
    answered at all. The window now shows a bounded extract and says how many
    lines were left out.
    """

    spec = importlib.util.spec_from_file_location(
        'installer_update_ui', Path(__file__).parents[1] / 'scripts/installer-update-ui.py')
    ui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ui)

    def test_short_notes_are_shown_whole(self):
        notes = 'One line.' + chr(10) + 'Another line.'
        self.assertEqual(notes, self.ui.summarise(notes))

    def test_long_notes_are_bounded_and_say_what_is_missing(self):
        notes = (chr(10)).join('Line %d of the release notes.' % n for n in range(1, 95))
        short = self.ui.summarise(notes)
        self.assertLessEqual(len(short.splitlines()), 17)
        self.assertLess(len(short), 1100)
        self.assertIn('more lines', short)
        self.assertIn('Line 1 of the release notes.', short)
        self.assertNotIn('Line 94 of the release notes.', short)

    def test_the_real_release_notes_fit(self):
        notes = (Path(__file__).parents[1] / '.verify-work/release-notes-016.md')
        if not notes.exists():
            self.skipTest('release notes are workshop only')
        short = self.ui.summarise(notes.read_text(encoding='utf-8'))
        self.assertLessEqual(len(short.splitlines()), 17)
        self.assertLess(len(short), 1100)


class SteamosCompatibilityIsRecordedNotEnforced(unittest.TestCase):
    """A declared version list must not block the releases people actually run.

    Every release so far declared 3.8.16. Valve moved stable to 3.8.28 on
    2026-09-22, so the published updater would have refused on current stable,
    and the next point release would do it again. The list now records what was
    tested: below the oldest entry there is nothing to stand on and the update
    still refuses, at or above it the update proceeds and says what it saw. The
    integration itself ends in pc_check_addons under set -e, so a release that
    genuinely does not fit fails there instead of degrading quietly.
    """

    def warn(self, version, tested=('3.8.16', '3.8.28')):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            m.check_steamos(version, list(tested), 'Release')
        return captured.getvalue()

    def test_a_tested_release_passes_without_saying_anything(self):
        self.assertEqual('', self.warn('3.8.28'))
        self.assertEqual('', self.warn('3.8.16'))

    def test_a_newer_point_release_passes_and_names_both_sides(self):
        message = self.warn('3.8.29')
        self.assertIn('3.8.29', message)
        self.assertIn('3.8.16', message)
        self.assertIn('3.8.28', message)

    def test_a_newer_series_passes_too(self):
        self.assertIn('3.9.1', self.warn('3.9.1'))

    def test_the_judgement_precedes_any_work_on_the_other_slot(self):
        # A refusal is only worth anything if nothing has been written yet. The
        # install path has to judge the running system before it hands the
        # transaction to driver-change, which clones the root into the other slot.
        source = (Path(__file__).parents[1] / 'scripts/installer-update.py').read_text(encoding='utf-8')
        self.assertEqual(1, source.count('check_steamos(d.manifest()'))
        self.assertEqual(1, source.count('d.install('))
        self.assertLess(source.index('check_steamos(d.manifest()'), source.index('d.install('),
                        'the version judgement has to come before the slot is prepared')

    def test_older_than_anything_tested_is_refused_and_names_the_oldest(self):
        with self.assertRaises(ValueError) as refusal:
            self.warn('3.8.15')
        self.assertIn('3.8.15', str(refusal.exception))
        self.assertIn('3.8.16', str(refusal.exception))

    def test_an_unreadable_version_warns_rather_than_crashing(self):
        self.assertIn('snapshot', self.warn('snapshot'))


class InstallerUpdate(unittest.TestCase):
    def test_overlay_artifact_is_all_or_nothing_and_old_bundles_remain_valid(self):
        value = manifest()
        for name in m.OPTIONAL_FILES:
            del value['files'][name]
        m.validate_manifest(value)
        for name in m.OPTIONAL_FILES:
            partial = dict(value, files={**value['files'], name: '0'*64})
            with self.subTest(name=name), self.assertRaises(ValueError):
                m.validate_manifest(partial)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bundle.tar'
            with tarfile.open(path, 'w') as archive:
                for name in value['files']:
                    member = tarfile.TarInfo(name); member.size = 4
                    archive.addfile(member, io.BytesIO(b'test'))
            value['bundle_sha256'] = m.digest(path.read_bytes())
            self.assertEqual(set(m.read_bundle(path, value)), set(value['files']))
            with tarfile.open(path, 'a') as archive:
                member = tarfile.TarInfo('mangoapp'); member.size = 4
                archive.addfile(member, io.BytesIO(b'test'))
            value['bundle_sha256'] = m.digest(path.read_bytes())
            with self.assertRaises(ValueError):
                m.read_bundle(path, value)

    def test_manifest_rejects_a_newer_format_and_invalid_values(self):
        for changed in [dict(format=2), dict(version='../bad'), dict(steamos=['*']),
                        dict(files={'../../etc/passwd':'0'*64}), dict(bundle_sha256='bad')]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                m.validate_manifest(dict(manifest(), **changed))
        m.validate_manifest(manifest())

    def test_archive_integrity_and_member_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bundle.tar'
            for bad in ('symlink', 'traversal', 'duplicate', 'missing', 'checksum', None):
                with tarfile.open(path,'w') as archive:
                    for name in m.FILES:
                        if bad=='missing' and name=='pc-support.sh':continue
                        member=tarfile.TarInfo(name); member.size=4
                        archive.addfile(member,io.BytesIO(b'test'))
                    if bad in ('symlink','traversal','duplicate'):
                        member=tarfile.TarInfo('../outside' if bad=='traversal' else 'pc-support.sh')
                        if bad=='symlink':member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd'
                        archive.addfile(member)
                value=manifest();value['bundle_sha256']=m.digest(path.read_bytes())
                if bad=='checksum':value['files']['pc-support.sh']='1'*64
                if bad:
                    with self.subTest(bad=bad),self.assertRaises(ValueError):m.read_bundle(path,value)
                else:self.assertEqual(set(m.read_bundle(path,value)),set(m.FILES))
                self.assertFalse((Path(tmp)/'outside').exists())

    def test_signature_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);key=folder/'private.pem';pub=folder/'public.pem'
            subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(key)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-out',str(pub)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            data=folder/'manifest';sig=folder/'signature';data.write_bytes(b'original')
            subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(key),'-rawin','-in',str(data),'-out',str(sig)],check=True)
            m.verify_signature(data,sig,pub.read_text(),folder)
            data.write_bytes(b'changed')
            with self.assertRaises(subprocess.CalledProcessError):m.verify_signature(data,sig,pub.read_text(),folder)

    def test_plain_http_is_rejected_before_download(self):
        with patch.object(m.subprocess,'run') as run:
            with self.assertRaises(ValueError):m.download('http://example.com/file',Path('/tmp/no'),100)
            run.assert_not_called()

    def test_release_pins_signed_version_and_selected_digest(self):
        source=(Path(__file__).parents[1]/'scripts/installer-update.py').read_text()
        self.assertIn("release['tag_name'] != 'v' + value['version']",source)
        self.assertIn("value['manifest_sha256'] != args.manifest_sha256",source)

    def test_transaction_does_not_reuse_source_completion(self):
        stage=(Path(__file__).parents[1]/'scripts/driver-stage.sh').read_text()
        self.assertLess(stage.index('rm -f "$work/target/usr/lib/steamos-nvidia/complete"'),stage.index('dd if='))
        installer=(Path(__file__).parents[1]/'steamos-nvidia-installer.sh').read_text()
        repatch=installer.split("<<'REPATCH'\n",1)[1].split('\nREPATCH\n',1)[0]
        self.assertLess(repatch.index('apply-target "$NEWROOT"'),repatch.index('pc_write_complete "$NEWROOT"'))

    def test_source_rejects_untrusted_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config';path.write_text('{}');path.chmod(0o666)
            with patch.object(m,'CONFIG',path),self.assertRaises(ValueError):m.source()

    def test_asset_downloads_use_configured_origin(self):
        cfg=dict(name='test',release_api='https://api.example.com/repos/o/r/releases/',
                 download_origin='https://downloads.example.com',allow_prerelease=True,public_key='unused')
        release=dict(tag_name='v0.1.0-dev.1',prerelease=True,draft=False,assets=[
            dict(name=n,browser_download_url='https://old.example.com/releases/'+n)
            for n in ['installer-manifest.json','installer-manifest.sig']])
        calls=[]
        def download(url,target,limit):
            calls.append(url)
            if target.name=='release.json':target.write_text(json.dumps([release]))
            elif target.name=='installer-manifest.json':target.write_text(json.dumps(manifest()))
            else:target.write_bytes(b'signature')
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'source',return_value=cfg),patch.object(m,'download',side_effect=download),patch.object(m,'verify_signature'):
            value=m.fetch('latest',Path(tmp))
            self.assertEqual(value['version'],'0.1.0-dev.1')
            self.assertTrue(all(u.startswith(cfg['download_origin']) for u in calls[1:]))
            self.assertEqual(value['page'],
                             'https://downloads.example.com/o/r/releases/tag/v0.1.0-dev.1')

    def test_the_release_page_is_named_and_pinned_to_the_configured_origin(self):
        # The window tells the reader the notes are cut short, so it has to say
        # where the rest is. The address must not come from the server.
        github=dict(release_api='https://api.github.com/repos/60plus/steamos-nvidia-installer/releases/',
                    download_origin='https://github.com')
        custom=dict(release_api='https://git.example.com/api/v1/repos/o/r/releases/',
                   download_origin='https://git.example.com')
        self.assertEqual(m.release_page(github,'v0.1.7'),
                         'https://github.com/60plus/steamos-nvidia-installer/releases/tag/v0.1.7')
        self.assertEqual(m.release_page(custom,'v0.1.7'),
                         'https://git.example.com/o/r/releases/tag/v0.1.7')
        hostile=dict(release_api='https://api.example.com/repos/o/r/releases/',
                     download_origin='https://downloads.example.com')
        self.assertTrue(m.release_page(hostile,'v1').startswith('https://downloads.example.com/'))

    def test_stable_source_rejects_prerelease_before_asset_download(self):
        cfg=dict(name='stable',release_api='https://api.example.com/repos/o/r/releases/',allow_prerelease=False)
        def download(url,target,limit):target.write_text(json.dumps({'prerelease':True}))
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'source',return_value=cfg),patch.object(m,'download',side_effect=download) as fetch:
            with self.assertRaises(ValueError):m.fetch('latest',Path(tmp))
            self.assertEqual(fetch.call_count,1)

    def test_btrfs_target_uses_source_device_and_rejects_active_root(self):
        import stat
        from types import SimpleNamespace
        def info(path):
            return SimpleNamespace(st_mode=stat.S_IFBLK,st_rdev=1 if 'self' in str(path) or str(path)=='/dev/vda4' else 2)
        with patch.object(m.os,'stat',side_effect=info):
            m.verify_target_device('/target',lambda *a:'/dev/vda5[/]')
            with self.assertRaises(ValueError):m.verify_target_device('/target',lambda *a:'/dev/vda4')
            with self.assertRaises(ValueError):m.verify_target_device('/target',lambda *a:'overlay')


class GamescopeCanNowBeDeliveredByAnUpdate(unittest.TestCase):
    """Gamescope used to be reachable only by installing a whole new image.

    It belonged with the driver, among the things that cost a new image, a destructive
    install and the first OS update to change, because the signed bundle could not
    carry it. Its three files are now in the bundle's list at the paths
    `pc_install_gamescope` reads, and that function already runs at the end of every
    transaction, so it verifies the binary against its own provenance, refuses a
    commit it does not recognise and writes the session override with no new code.

    An installed 0.1.8 will ignore these three names and say so, which is what makes
    the first release safe to publish: it teaches the installed tool the names, and
    the release after it delivers the binary.
    """

    ROOT = Path(__file__).parents[1]

    def test_the_three_files_land_where_the_installer_looks_for_them(self):
        self.assertEqual(m.FILES['gamescope'], ('usr/lib/steamos-nvidia/gamescope/bin/gamescope', 0o755))
        for name in ('gamescope-build.json', 'Gamescope-LICENSE'):
            with self.subTest(name=name):
                self.assertEqual(m.FILES[name], ('usr/lib/steamos-nvidia/gamescope/' + name, 0o644))
        support = (self.ROOT / 'lib/pc-support.sh').read_text()
        # The paths above are only correct if they are the ones that function reads.
        self.assertIn('base="$1/usr/lib/steamos-nvidia/gamescope"', support)
        self.assertIn("(p/'bin/gamescope')", support)
        self.assertIn("(p/'Gamescope-LICENSE')", support)
        self.assertIn("(p/'gamescope-build.json')", support)

    def test_every_optional_group_is_all_or_nothing_on_its_own(self):
        # The overlay and Gamescope are independent: carrying one in full and not the
        # other is a valid release, and half of either is not.
        for group_name, group in m.OPTIONAL_GROUPS.items():
            value = manifest()
            for name in group:
                del value['files'][name]
            with self.subTest(group=group_name, case='absent in full'):
                m.validate_manifest(value)
            for name in sorted(group):
                partial = dict(value, files={**value['files'], name: '0' * 64})
                with self.subTest(group=group_name, partial=name), self.assertRaises(ValueError):
                    m.validate_manifest(partial)

    def test_the_transaction_already_installs_and_re_verifies_it(self):
        source = (self.ROOT / 'scripts/installer-update.py').read_text()
        self.assertIn('pc_install_gamescope "$1"', source)
        self.assertIn('pc_write_addon_manifest "$1"', source)
        self.assertIn('pc_check_addons "$1"', source)

    def test_the_release_builder_carries_it_only_when_asked(self):
        builder = (self.ROOT / 'tools/build-installer-release.py').read_text()
        self.assertIn('--gamescope-dir', builder)
        self.assertIn("'gamescope': gamescope_dir", builder)
        # A bundle built without the directory must stay valid, which is the same
        # property the overlay has relied on since 0.1.2.
        self.assertIn('if sources[group] is not None:', builder)


class TheBundleCanGainFilesWithoutStrandingAnyone(unittest.TestCase):
    """A release may carry files an installed version does not know about.

    Measured on 2026-09-26: an installed tool validates a new release against the
    file list it was built with, so a manifest naming one unknown file was refused
    whole with `Release has missing or unexpected files`. The update window only
    ever offers the latest release, so the first release to add a file would have
    stranded every older installation. The list could therefore never change, which
    is why the notification renderer could not be fixed by an update at all.

    Unknown names and unknown fields are now ignored and named. `format` stays
    strict, so a change that must not be half applied can still refuse cleanly.
    """

    def manifest_with(self, **files):
        value = manifest()
        return dict(value, files={**value['files'], **files})

    def quietly(self, call, *args):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            result = call(*args)
        return result, captured.getvalue()

    def validated(self, value):
        # The note belongs to the assertion that looks for it, not to every other
        # test's output.
        return self.quietly(m.validate_manifest, value)[0]

    def test_an_unknown_file_is_accepted_and_named(self):
        _, said = self.quietly(m.validate_manifest, self.manifest_with(**{'notification-renderer.py': '0' * 64}))
        self.assertIn('notification-renderer.py', said)
        self.assertIn('does not install', said)

    def test_an_unknown_field_is_ignored_but_a_newer_format_is_refused(self):
        m.validate_manifest(dict(manifest(), requires_tool='0.1.9'))
        with self.assertRaises(ValueError):
            m.validate_manifest(dict(manifest(), format=2))

    def test_a_file_this_version_requires_is_still_mandatory(self):
        value = manifest()
        del value['files']['pc-support.sh']
        with self.assertRaises(ValueError):
            m.validate_manifest(value)

    def test_an_unreasonable_name_or_count_is_refused(self):
        with self.assertRaises(ValueError):
            m.validate_manifest(self.manifest_with(**{'../outside': '0' * 64}))
        with self.assertRaises(ValueError):
            m.validate_manifest(self.manifest_with(**{f'extra{i}': '0' * 64 for i in range(m.MAX_FILES)}))

    def bundle(self, folder, value, contents):
        path = Path(folder) / 'bundle.tar'
        with tarfile.open(path, 'w') as archive:
            for name in value['files']:
                data = contents.get(name, b'test')
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        value['bundle_sha256'] = m.digest(path.read_bytes())
        return path

    def test_an_unknown_member_is_checked_but_not_handed_back_to_be_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = self.manifest_with(**{'notification-renderer.py': m.digest(b'newer')})
            path = self.bundle(tmp, value, {'notification-renderer.py': b'newer'})
            payload, _ = self.quietly(m.read_bundle, path, self.validated(value))
            self.assertEqual(set(m.FILES), set(payload))
            self.assertNotIn('notification-renderer.py', payload)

    def test_an_unknown_member_that_does_not_match_breaks_the_whole_release(self):
        # The signature covers every name in the manifest, so a member that does not
        # match is a broken release even if this version would not install it.
        with tempfile.TemporaryDirectory() as tmp:
            value = self.manifest_with(**{'notification-renderer.py': '1' * 64})
            path = self.bundle(tmp, value, {})
            with self.assertRaises(ValueError):
                self.quietly(m.read_bundle, path, self.validated(value))

    def test_an_unknown_name_the_archive_omits_breaks_the_whole_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = self.manifest_with(**{'notification-renderer.py': m.digest(b'newer')})
            self.bundle(tmp, value, {'notification-renderer.py': b'newer'})
            missing = dict(value)
            path = Path(tmp) / 'bundle.tar'
            with tarfile.open(path, 'w') as archive:
                for name in [n for n in value['files'] if n != 'notification-renderer.py']:
                    member = tarfile.TarInfo(name)
                    member.size = 4
                    archive.addfile(member, io.BytesIO(b'test'))
            missing['bundle_sha256'] = m.digest(path.read_bytes())
            with self.assertRaises(ValueError):
                self.quietly(m.read_bundle, path, self.validated(missing))


CLEAN = {'missing': [], 'different': [], 'invalid': []}


class VersionsAreOrderedRatherThanCompared(unittest.TestCase):
    """The update window asked only whether the two version strings were equal.

    A machine ahead of its source was therefore offered a downgrade instead of being told it
    is up to date, which happens on any machine that took a prerelease and on every machine
    while the next release is being prepared.
    """

    def test_a_newer_release_is_offered(self):
        self.assertEqual(m.offer(dict(version='0.2.1'), '0.2.0', CLEAN), 'install')

    def test_a_machine_ahead_of_its_source_is_left_alone(self):
        self.assertEqual(m.offer(dict(version='0.2.0'), '0.2.1', CLEAN), 'none')

    def test_point_releases_are_not_compared_as_text(self):
        # '0.1.10' sorts below '0.1.9' as text, which is the trap this replaces.
        self.assertGreater(m.version_key('0.1.10'), m.version_key('0.1.9'))

    def test_a_prerelease_sorts_below_the_release_it_leads_to(self):
        self.assertLess(m.version_key('0.2.0-rc.1'), m.version_key('0.2.0'))
        self.assertLess(m.version_key('0.2.0-rc.1'), m.version_key('0.2.0-rc.2'))

    def test_a_hyphen_inside_an_identifier_is_not_a_separator(self):
        # The accepted grammar allows one, and splitting on it as well put 0.2.1-rc-1 below
        # 0.2.1-rc.2. It is a single identifier, compared as text against 'rc', so it sorts
        # above it.
        self.assertGreater(m.version_key('0.2.1-rc-1'), m.version_key('0.2.1-rc.2'))

    def test_a_numeric_identifier_sorts_below_an_alphanumeric_one(self):
        self.assertLess(m.version_key('0.2.0-1'), m.version_key('0.2.0-alpha'))

    def test_an_unreadable_or_absent_version_sorts_below_everything(self):
        for value in ('unknown', '', None, 3, 'not a version'):
            with self.subTest(value=value):
                self.assertEqual(m.version_key(value), ())
        self.assertEqual(m.offer(dict(version='0.1.0'), 'unknown', CLEAN), 'install')


class DamagedVersionMetadataRecoversToUnknown(unittest.TestCase):
    """installed() read that file with no guard at all.

    Malformed JSON, a missing key or a version that is not a string each raised, and the
    caller turned that into a failed check rather than an offer. Recovering to 'unknown'
    offers the newest release, which writes the whole payload again, so the safe answer and
    the recovery agree.
    """

    def answer(self, text=None, as_directory=False):
        folder = tempfile.TemporaryDirectory(prefix='installed-')
        self.addCleanup(folder.cleanup)
        base = Path(folder.name)
        target = base / 'integration-version.json'
        if as_directory:
            target.mkdir()
        elif text is not None:
            target.write_text(text)
        with patch.object(m, 'BASE', base):
            return m.installed()

    def test_a_good_file_is_read(self):
        self.assertEqual(self.answer(json.dumps({'version': '0.2.0'})), '0.2.0')

    def test_absent_malformed_and_wrongly_typed_all_answer_unknown(self):
        for case, text in (('absent', None), ('not json', '{'), ('no key', '{}'),
                           ('a list', '[]'), ('a number', json.dumps({'version': 3})),
                           ('null', json.dumps({'version': None}))):
            with self.subTest(case=case):
                self.assertEqual(self.answer(text), 'unknown')

    def test_a_directory_in_its_place_answers_unknown(self):
        self.assertEqual(self.answer(as_directory=True), 'unknown')


class AReleaseCanBeInstalledAgainToConvergeOnIt(unittest.TestCase):
    """Presence is not enough, which is the correction the review made to the first attempt.

    A machine on tools 0.1.8 that installed a release carrying Gamescope had the three files
    skipped, because an installed tool writes only the names it was built knowing. It then
    reported the new version and the updater offered nothing. Looking for files that are
    absent misses the documented form of this fault: a complete image already carries
    Gamescope at exactly these destinations, so the old binary is cloned forward and the
    destination exists holding the wrong bytes.

    The invariant: updating the integration tools must also replace an older
    optional Gamescope artifact. Checking only the helper version can leave the
    compositor unchanged, and the machine then reports itself up to date without
    the correction.
    """

    GROUP = 'gamescope'

    def tree(self, missing=(), stale=(), directories=()):
        folder = tempfile.TemporaryDirectory(prefix='payload-')
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        for name, (rel, _) in m.FILES.items():
            if name in missing:
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if name in directories:
                target.mkdir()
            else:
                target.write_bytes(b'previous build' if name in stale else b'test')
        return root

    def test_a_complete_system_matches_the_release(self):
        state = m.payload_state(manifest(), self.tree())
        self.assertEqual(m.damaged(state), [])
        self.assertEqual(m.offer(manifest(), manifest()['version'], state), 'none')

    def test_an_existing_older_binary_is_not_healthy(self):
        # The blocking counterexample. Every destination exists, the version matches, and the
        # bytes are the previous build's.
        root = self.tree(stale=m.OPTIONAL_GROUPS[self.GROUP])
        state = m.payload_state(manifest(), root)
        self.assertEqual(state['missing'], [])
        self.assertEqual(state['different'], sorted(m.OPTIONAL_GROUPS[self.GROUP]))
        self.assertEqual(m.offer(manifest(), manifest()['version'], state), 'repair')

    def test_the_recorded_manifest_hash_does_not_suppress_it(self):
        # An old tool authenticates the whole manifest and records its hash while deliberately
        # skipping names it does not know, so that value is a receipt for the transaction and
        # not evidence that every member was written. Nothing in the decision reads it.
        source = (Path(__file__).parents[1] / 'scripts/installer-update.py').read_text()
        decision = source[source.index('def payload_state'):source.index('def verify_target_device')]
        self.assertNotIn('manifest_sha256', decision)

    def test_a_whole_absent_group_and_a_single_absent_member_both_count(self):
        group = m.OPTIONAL_GROUPS[self.GROUP]
        whole = m.payload_state(manifest(), self.tree(missing=group))
        self.assertEqual(whole['missing'], sorted(group))
        one = m.payload_state(manifest(), self.tree(missing={'gamescope'}))
        self.assertEqual(one['missing'], ['gamescope'])
        self.assertEqual(m.offer(manifest(), manifest()['version'], one), 'repair')

    def test_a_release_that_does_not_carry_the_group_asks_for_nothing(self):
        # A base only image legitimately has no Gamescope. A release that does not carry it
        # has nothing to put there, so there is nothing to converge on.
        value = manifest()
        for name in m.OPTIONAL_GROUPS[self.GROUP]:
            del value['files'][name]
        state = m.payload_state(value, self.tree(missing=m.OPTIONAL_GROUPS[self.GROUP]))
        self.assertEqual(m.damaged(state), [])
        self.assertEqual(m.offer(value, value['version'], state), 'none')

    def test_a_base_only_tree_converges_on_a_release_that_carries_it(self):
        # The other half of the same case, and it is deliberate: nothing persists a choice
        # that this machine must stay without Gamescope, and every ordinary update already
        # delivers every file the release carries.
        state = m.payload_state(manifest(), self.tree(missing=m.OPTIONAL_GROUPS[self.GROUP]))
        self.assertEqual(m.offer(manifest(), manifest()['version'], state), 'repair')

    def test_a_name_this_version_cannot_place_is_never_reported(self):
        # The mirror of the rule that lets a release carry names a later version knows.
        # Reporting one would ask for a repair that could never put it anywhere.
        value = manifest()
        value['files']['something-a-later-version-knows'] = '0' * 64
        self.assertEqual(m.damaged(m.payload_state(value, self.tree())), [])

    def test_a_directory_at_a_destination_is_not_a_healthy_file(self):
        # Path.exists() answers true for a directory, so presence alone called this healthy.
        state = m.payload_state(manifest(), self.tree(directories={'gamescope'}))
        self.assertEqual(state['invalid'], ['gamescope'])
        self.assertEqual(state['missing'], [])
        self.assertEqual(m.offer(manifest(), manifest()['version'], state), 'repair')

    def test_the_refusal_is_measured_again_under_the_lock(self):
        source = (Path(__file__).parents[1] / 'scripts/installer-update.py').read_text()
        self.assertIn("if value['version'] == installed() and not damaged(payload_state(value)):", source)
        self.assertIn("raise ValueError('This integration version is already installed')", source)

    def test_the_check_publishes_the_state_and_the_decision(self):
        source = (Path(__file__).parents[1] / 'scripts/installer-update.py').read_text()
        self.assertIn('payload=state', source)
        self.assertIn('offer=offer(value, current, state)', source)

    def test_the_payload_is_only_reported_against_the_installed_version(self):
        # Measured on the test machine on 2026-09-29. It had 0.2.1 and its source offered
        # 0.2.0, so comparing the payload against that older release named the Gamescope
        # files as different. They are not damaged: the machine is ahead. The check now
        # reports the comparison only when it means something.
        source = (Path(__file__).parents[1] / 'scripts/installer-update.py').read_text()
        self.assertIn("state = payload_state(value) if value['version'] == current else EMPTY_PAYLOAD", source)
        self.assertEqual(m.EMPTY_PAYLOAD, {'missing': [], 'different': [], 'invalid': []})
        self.assertEqual(m.damaged(m.EMPTY_PAYLOAD), [])
        # And the decision is unaffected, because an unequal version never reads the payload.
        self.assertEqual(m.offer(dict(version='0.2.0'), '0.2.1', m.EMPTY_PAYLOAD), 'none')
        self.assertEqual(m.offer(dict(version='0.2.2'), '0.2.1', m.EMPTY_PAYLOAD), 'install')
