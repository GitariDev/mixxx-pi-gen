"""Compile and exercise the real mount parser shipped in the pinned Mixxx patch.

The complete Mixxx/Qt build and live insertion/playback checks remain required
before calling the feature device-tested. These tests cover mount selection,
escaped paths, separate devices and same-path replacement identity.
"""
from pathlib import Path
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "stage3/01-install-packages/files/mixxx-media-hotplug.patch"
HEADER = "src/library/rekordbox/removablemounts.h"


def added_lines(path):
    """Read added source lines from one file in the version-pinned patch."""
    lines = PATCH.read_text().splitlines(keepends=True)
    active = False
    result = []
    for line in lines:
        if line.startswith("diff --git "):
            active = line.rstrip() == f"diff --git a/{path} b/{path}"
        elif active and line.startswith("+") and not line.startswith("+++"):
            result.append(line[1:])
    if not result:
        raise AssertionError(f"added source missing from patch: {path}")
    return "".join(result)


@unittest.skipUnless(shutil.which("c++"), "C++ compiler required")
class RemovableMountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        target = Path(cls.directory.name)
        (target / "removablemounts.h").write_text(added_lines(HEADER))
        (target / "main.cpp").write_text(r'''
#include "removablemounts.h"
#include <iostream>
int main(int argc, char** argv) {
    std::vector<std::string> directories;
    for (int i = 1; i < argc; ++i) {
        directories.emplace_back(argv[i]);
    }
    const auto mounts = mixxx::rekordbox::addExportDirectories(
        mixxx::rekordbox::readRemovableMounts(std::cin), directories);
    for (const auto& [path, identity] : mounts) {
        std::cout << path << '\0' << identity << '\0';
    }
}
''')
        cls.executable = target / "mount-parser"
        subprocess.run(
            ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
             str(target / "main.cpp"), "-o", str(cls.executable)],
            check=True, capture_output=True, text=True,
        )

    def parse(self, mounts, directories=()):
        raw = subprocess.run(
            [str(self.executable), *directories], input=mounts.encode(),
            capture_output=True, check=True,
        ).stdout
        parts = raw.decode().split("\0")[:-1]
        return dict(zip(parts[::2], parts[1::2]))

    def test_excludes_system_mounts(self):
        mounts = self.parse("""25 1 179:2 / / rw - ext4 /dev/mmcblk0p2 rw
26 25 179:1 / /boot/firmware rw - vfat /dev/mmcblk0p1 rw
27 25 0:29 / /run/user/1000 rw - tmpfs tmpfs rw
28 25 8:1 / /media/pi/MANTACORE rw - exfat /dev/sda1 rw
""")
        self.assertEqual(mounts, {"/media/pi/MANTACORE": "28:8:1:/"})

    def test_duplicate_labels_on_separate_mount_roots(self):
        mounts = self.parse("""28 25 8:1 / /media/pi/Guest rw - exfat /dev/sda1 rw
29 25 8:17 / /run/media/pi/Guest ro - vfat /dev/sdb1 ro
""")
        self.assertEqual(mounts, {
            "/media/pi/Guest": "28:8:1:/",
            "/run/media/pi/Guest": "29:8:17:/",
        })

    def test_escaped_spaces_unicode_and_literal_backslashes(self):
        mounts = self.parse(
            r"28 25 8:1 / /media/pi/ሙዚቃ\040Guest\134040 rw - exfat /dev/sda1 rw" + "\n"
        )
        self.assertEqual(mounts, {"/media/pi/ሙዚቃ Guest\\040": "28:8:1:/"})

    def test_same_path_replacement_changes_identity(self):
        first = self.parse("28 25 8:1 / /media/pi/Guest rw - exfat /dev/sda1 rw\n")
        replacement = self.parse("35 25 8:1 / /media/pi/Guest rw - exfat /dev/sda1 rw\n")
        self.assertNotEqual(first, replacement)
        self.assertEqual(list(first), list(replacement))

    def test_unmount_and_order_independence(self):
        a = "28 25 8:1 / /media/pi/A rw - exfat /dev/sda1 rw\n"
        b = "29 25 8:17 / /media/pi/B rw - exfat /dev/sdb1 rw\n"
        self.assertEqual(self.parse(a + b), self.parse(b + a))
        self.assertEqual(list(self.parse(b)), ["/media/pi/B"])
        self.assertEqual(self.parse(""), {})

    def test_preserves_sd_backup_and_copied_exports_with_usb(self):
        mounts = self.parse(
            "28 25 8:1 / /media/pi/MANTACORE rw - exfat /dev/sda1 rw\n",
            ["/media/SD-Backup", "/media/pi/MixPi-EthioJazz", "/media/pi/MANTACORE"],
        )
        self.assertEqual(mounts, {
            "/media/SD-Backup": "directory:/media/SD-Backup",
            "/media/pi/MixPi-EthioJazz": "directory:/media/pi/MixPi-EthioJazz",
            "/media/pi/MANTACORE": "28:8:1:/",
        })

    def test_local_export_publication_and_removal_without_mount_event(self):
        initial = self.parse("", ["/media/SD-Backup"])
        published = self.parse("", ["/media/SD-Backup", "/media/pi/MixPi-Guest"])
        self.assertNotEqual(initial, published)
        self.assertEqual(len(published), 2)
        self.assertEqual(self.parse("", ["/media/SD-Backup"]), initial)

    def test_malformed_records_and_prefix_lookalikes(self):
        mounts = self.parse("""bad line
29 25 8:1 / /media-backup/Guest rw - exfat /dev/sda1 rw
30 25 8:1 / /run/media-backup/Guest rw - exfat /dev/sda1 rw
""")
        self.assertEqual(mounts, {})


class DeviceCleanupTests(unittest.TestCase):
    def test_handover_cleanup_preserves_other_device_and_allows_reinsertion(self):
        # Execute the native queries from the patch, rather than a second
        # implementation of the cleanup algorithm. Include an empty folder,
        # an empty playlist, Unicode, and SQL wildcard characters in a label.
        source = added_lines("src/library/rekordbox/rekordboxfeature.cpp")
        constants = {
            "kRekordboxPlaylistsTable": "rekordbox_playlists",
            "kRekordboxPlaylistTracksTable": "rekordbox_playlist_tracks",
            "kRekordboxLibraryTable": "rekordbox_library",
        }

        def expression(value):
            tokens = re.findall(r'"(?:[^"\\]|\\.)*"|[A-Za-z_]\w*', value)
            return "".join(json.loads(token) if token.startswith('"') else constants[token]
                           for token in tokens)

        constants["ownedPlaylists"] = expression(re.search(
            r"const QString ownedPlaylists = (.*?);", source, re.S)[1])
        queries = [expression(re.search(name + r"\.prepare\((.*?)\);", source, re.S)[1])
                   for name in ("deletePlaylistTracks", "deletePlaylists", "deleteTracks")]
        with sqlite3.connect(":memory:") as db:
            db.executescript("""
                CREATE TABLE rekordbox_playlists (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
                CREATE TABLE rekordbox_playlist_tracks (playlist_id INTEGER, track_id INTEGER);
                CREATE TABLE rekordbox_library (id INTEGER PRIMARY KEY, device TEXT);
            """)
            a = "/media/pi/Guest_%😀"
            b = "/media/pi/Guest_%😀-two"
            playlists = [(1, a), (2, a + "-->Folder"), (3, a + "-->Folder-->Set"),
                         (4, a + "-->Empty"), (5, b), (6, b + "-->Set")]
            db.executemany("INSERT INTO rekordbox_playlists VALUES (?, ?)", playlists)
            db.executemany("INSERT INTO rekordbox_library VALUES (?, ?)", [(1, a), (2, b)])
            db.executemany("INSERT INTO rekordbox_playlist_tracks VALUES (?, ?)",
                           [(1, 1), (3, 1), (5, 2), (6, 2)])
            for query in queries:
                db.execute(query, {"device": a, "prefix": a + "-->"})
            self.assertEqual(db.execute("SELECT * FROM rekordbox_playlists ORDER BY id").fetchall(),
                             playlists[4:])
            self.assertEqual(db.execute("SELECT * FROM rekordbox_library").fetchall(), [(2, b)])
            self.assertEqual(db.execute("SELECT * FROM rekordbox_playlist_tracks").fetchall(),
                             [(5, 2), (6, 2)])
            db.executemany("INSERT INTO rekordbox_playlists VALUES (?, ?)", playlists[:4])
            self.assertEqual(db.execute("SELECT count(*) FROM rekordbox_playlists").fetchone(), (6,))


if __name__ == "__main__":
    unittest.main()
