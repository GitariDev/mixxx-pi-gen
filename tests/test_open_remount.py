"""Spec 2h (build M, wave J12): OPEN mounts an ejected drive again.

Owner, 2026-11-22: "No, we should be able to reload it if it is still
connected" and "You should be able to press open to mount again so the safe
to remove stays, but if you press open it goes back to a ready state".

Found before the change (build L):
- After a Media-page eject the row reads SAFE TO REMOVE and keeps its OPEN
  button, but OPEN is disabled there (MixpiMediaPage::openButton: not while
  ejecting or safe, and not without a mounted volume), so it does nothing.
- The eject retires the drive's read generation in MediaUseRegistry. The
  generation is keyed by the physical drive (boot id, mount namespace, sysfs
  node, dev, diskseq: mediause.h observePath, generationRevision), not by its
  mount, so a mount by other means (udisksctl mount) keeps it retired: Mixxx
  refuses its reads until a pull and re-plug (a new diskseq) or a restart.

mixxx-open-remount.patch:
- OPEN on a SAFE TO REMOVE row can be tapped. MixpiMedia::openVolume sends it
  to remountSafe: MixpiRemount (library/mixpimediaremount.h) mounts each
  volume the eject unmounted through udisks2 (udisksctl mount -b SOURCE
  --no-user-interaction, as the automounter asks udisks2), skips one that is
  mounted already, checks the mount table, and only then reopens the
  generations that eject retired (MediaUseRegistry::reopen: a new round).
- Then the row is READY (SAFE TO REMOVE and its strip go) and, once the
  inventory sees the mount, OPEN reads the drive as it always does.
- A drive pulled while SAFE TO REMOVE is not mounted; a failed mount leaves
  the generation retired and says so in build B's words.

The native checks are in tests/native/open_remount_test.cpp (built by
tests/native/open_remount_runner.py).
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

from native.library_interface_runner import qt_available
from native import library_interface_runner as RUNNER
from test_sample_browser import checks

ROOT = Path(__file__).resolve().parents[1]
PATCH = RUNNER.PATCH_DIR / 'mixxx-open-remount.patch'
TEST = ROOT / 'tests/native/open_remount_test.cpp'
MEDIA = 'src/library/mixpimedia.h'
PAGE = 'src/library/mixpimediapage.h'
REGISTRY = 'src/library/media/mediauseregistry.h'
REMOUNT = 'src/library/mixpimediaremount.h'


def changed(path, sign):
    text = PATCH.read_text()
    start = text.index('diff --git a/' + path + ' ')
    end = text.find('\ndiff --git', start + 1)
    return [line[1:] for line in text[start:end if end > 0 else None].splitlines()
            if line.startswith(sign) and not line.startswith(sign * 3)]


def added(path):
    return '\n'.join(changed(path, '+'))


class OpenRemountPatchTests(unittest.TestCase):
    def test_patch_changes_only_its_files(self):
        self.assertEqual(sorted(re.findall(r'^diff --git a/(\S+) b/\S+$', PATCH.read_text(), re.MULTILINE)),
                         sorted([REGISTRY, MEDIA, PAGE, REMOUNT]))
        self.assertIn('new file mode', PATCH.read_text().split('diff --git a/' + REMOUNT, 1)[1][:200])
        # Additions only, but for the two lines it widens.
        self.assertEqual([line.strip() for line in changed(MEDIA, '-')],
                         ['drive.identity != m_ejectingIdentity) {'])
        self.assertEqual([line.strip() for line in changed(PAGE, '-')],
                         ['open->setEnabled(!ending && !drive.volumes.isEmpty() && m_openingIdentity.isEmpty());'])
        self.assertEqual(changed(REGISTRY, '-'), [])

    def test_patch_is_registered_last(self):
        names = subprocess.check_output(['bash', str(ROOT / 'stage3/01-install-packages/01-run.sh'),
                                         '--mixxx-print-patches'], text=True).split()
        if PATCH.name not in names:
            self.skipTest(PATCH.name + ' is not registered yet')
        for prerequisite in ('mixxx-media-chip-ping.patch', 'mixxx-table-fit-media-open.patch',
                             'mixxx-eject-folders-view.patch', 'mixxx-removable-rows-fix.patch'):
            self.assertLess(names.index(prerequisite), names.index(PATCH.name))

    def test_open_on_a_safe_row_can_be_tapped(self):
        page = added(PAGE)
        self.assertIn('const bool remount = drive.state == MixpiMediaState::SafeToRemove;', page)
        self.assertIn('open->setEnabled((remount || (!ending && !drive.volumes.isEmpty())) && '
                      'm_openingIdentity.isEmpty());', page)
        # EJECT on that row stays off: its line is not changed.
        self.assertNotIn('eject->setEnabled', page)

    def test_open_on_the_safe_row_remounts(self):
        media = added(MEDIA)
        self.assertIn('if (!start && !m_safeIdentity.isEmpty() && identity == m_safeIdentity) {', media)
        self.assertIn('remountSafe(identity);', media)
        self.assertIn('const bool pluggedIn = !m_safeSysfs.isEmpty() && !driveGone(m_safeSysfs, m_safeDiskseq);',
                      media)
        # The eject records what it drained, unmounted and retired.
        self.assertIn('generations.push_back(generation);', media)
        self.assertIn('m_remount->drained(std::move(generations));', media)
        self.assertIn('m_remount->retired(m_ejectingIdentity, m_ejectVolumes, retired);', media)
        self.assertIn('m_ejectVolumes = volumes;', media)
        # After the inventory: OPEN's own read, as always.
        self.assertIn('openRemounted();', media)
        self.assertIn('openVolume(identity, volumes.first().toObject().value("token").toString());', media)
        self.assertIn('drive.identity != m_ejectingIdentity && drive.identity != m_remounted) {', media)
        self.assertIn('return mixxx::media::registry().reopen(generation);', media)
        self.assertIn('mixpiUdisksMount(this, source, std::move(done));', media)
        # The failure copy is build B's.
        self.assertEqual(media.count('QStringLiteral("This drive changed or could not be checked.")'), 2)

    def test_the_mount_is_the_systems_and_never_writes(self):
        remount = added(REMOUNT)
        self.assertIn('process->start(QStringLiteral("/usr/bin/udisksctl"),\n'
                      '            {QStringLiteral("mount"), QStringLiteral("-b"), source, '
                      'QStringLiteral("--no-user-interaction")});', remount)
        self.assertEqual(remount.count('QStringLiteral("/usr/bin/udisksctl")'), 1)
        # No mount options of its own, and nothing written.
        for writer in ('-o', 'QIODevice::WriteOnly', '.write(', 'setValue', 'remove(', 'rename('):
            self.assertNotIn(writer, remount)
        for writer in ('QIODevice::WriteOnly', '.write(', 'setValue'):
            self.assertNotIn(writer, added(MEDIA))

    def test_only_a_retired_generation_reopens(self):
        registry = added(REGISTRY)
        self.assertIn('if (entry == m_state->entries.end() || !entry->second.retired || entry->second.draining) {',
                      registry)
        self.assertIn('entry->second.retired = false;', registry)
        self.assertIn('++entry->second.round;', registry)

    def test_the_earlier_eject_fixtures_keep_their_methods(self):
        # J10 and J11 copy MixpiMedia::tick and ejectFinished: unchanged.
        text = PATCH.read_text().split('diff --git a/' + MEDIA, 1)[1].split('\ndiff --git', 1)[0]
        hunks = re.findall(r'^@@ .*$', text, re.MULTILINE)
        self.assertTrue(hunks)
        for line in changed(MEDIA, '+') + changed(MEDIA, '-'):
            self.assertNotIn('void tick()', line)
            self.assertNotIn('void ejectFinished(', line)


@unittest.skipUnless(qt_available(), 'Qt6 development dependencies required')
class OpenRemountNativeTests(unittest.TestCase):
    def run_fixture(self, *arguments):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'tests/native/open_remount_runner.py'),
                               *arguments], cwd=ROOT, capture_output=True, text=True, timeout=400)

    def test_native_open_remount(self):
        result = self.run_fixture()
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:] + result.stderr[-3000:])
        for check in checks(TEST):
            self.assertIn('PASS ' + check, result.stdout)
        self.assertNotIn('FAIL ', result.stdout)
        self.assertIn('OK 0', result.stdout)
        self.assertGreaterEqual(len(checks(TEST)), 25)

    def test_checks_fail_without_the_patch(self):
        result = self.run_fixture('--baseline')
        print(result.stdout[-4000:], result.stderr[-2000:], flush=True)
        self.assertNotEqual(result.returncode, 0)
        for check in ('eject: OPEN on the SAFE TO REMOVE row can be tapped',
                      'OPEN asks udisks2 to mount the drive\'s volume (mount -b /dev/sdz1 --no-user-interaction)',
                      'OPEN: GANDER1 is mounted again through udisks2 (no re-plug)',
                      'OPEN: GANDER1\'s read generation reopens as a new round',
                      'OPEN: GANDER1\'s tracks load to decks again',
                      'OPEN: Folders reads GANDER1\'s full tags again',
                      'OPEN: OPEN\'s normal read of the remounted volume runs',
                      'OPEN: GANDER1\'s row reads READY',
                      'OPEN on a drive mounted by hand: no second mount, a new round, reads allowed'):
            self.assertIn('FAIL ' + check, result.stdout)
        # Build B's eject rule holds without this patch.
        for check in ('eject: GANDER1\'s volume unmounted through udisks2',
                      'eject: GANDER1\'s reads are refused (its generation is retired)',
                      'eject: GANDER1\'s row reads SAFE TO REMOVE',
                      'eject: the SAFE TO REMOVE row keeps its OPEN button',
                      'eject: IXIAN still reads and reads READY'):
            self.assertIn('PASS ' + check, result.stdout)


if __name__ == '__main__':
    unittest.main()
