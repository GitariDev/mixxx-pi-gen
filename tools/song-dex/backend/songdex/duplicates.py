"""Actionable duplicates: suggest the entry to keep and merge the others into it.

A merge moves playlist places and My Tags to the kept entry and lists the leftover
entries in one rekordbox playlist. Removing them from the collection stays a
rekordbox action; Song Dex never deletes collection rows or files.

Marking a group as okay records the entries that stay separate, such as remixes
and other versions. Entries merged out of the group keep waiting for removal.
"""

from __future__ import annotations

from . import rekordbox

FOLDER, REMOVAL = "Song Dex", "Duplicates to remove"
LOSSLESS = {"FLAC", "WAV", "AIFF", "AIF"}


def awaiting_removal(track):
    return any(p["name"] == f"{FOLDER} / {REMOVAL}" for p in track["playlists"])


def strength(track):
    """Sort key for the entry worth keeping; cues and grids cannot be moved, so they lead."""
    m, stats = track["metadata"], track.get("stats") or {}
    return (
        bool(track["available"]),
        stats.get("cues", 0) > 0,
        str(m.get("format", "")).upper() in LOSSLESS,
        m.get("bitrate") or 0,
        len(track["playlists"]),
        len(track["my_tags"]),
        stats.get("plays", 0),
        stats.get("rating", 0),
        -track["id"],
    )


class Duplicates:
    def __init__(self, operations):
        self.operations = operations
        self.service, self.store = operations.service, operations.store

    def groups(self, tracks=None):
        tracks = tracks or self.store.tracks()
        by_id = {t["id"]: t for t in tracks}
        dismissed = [set(ids) for ids in self.store.setting("duplicates_dismissed", [])]
        groups = []
        for group in self.service.duplicates(tracks):
            ids = group["tracks"]
            waiting = [i for i in ids if awaiting_removal(by_id[i])]
            open_ids = [i for i in ids if i not in waiting]
            # Only the entries left open were okayed, so a restored merge reopens the group.
            okayed = any(set(open_ids) <= known for known in dismissed)
            if okayed and not waiting:
                continue
            groups.append(
                {
                    **group,
                    "keep": max(open_ids or ids, key=lambda i: strength(by_id[i])),
                    "awaiting_removal": waiting,
                    "merged": okayed or len(open_ids) < 2,
                }
            )
        return groups

    def dismiss(self, groups):
        current = {frozenset(g["tracks"]): g for g in self.groups()}
        if any(frozenset(ids) not in current for ids in groups):
            raise ValueError("Duplicate groups changed; refresh and review again")
        self.okay(
            set(ids) - set(current[frozenset(ids)]["awaiting_removal"])
            for ids in groups
        )
        self.store.log("duplicates", f"Marked {len(groups)} groups as okay")
        return {"dismissed": len(self.store.setting("duplicates_dismissed", []))}

    def okay(self, groups):
        known = self.store.setting("duplicates_dismissed", [])
        self.store.set_setting(
            "duplicates_dismissed", [*known, *(sorted(ids) for ids in groups)]
        )

    def reset_dismissed(self):
        self.store.set_setting("duplicates_dismissed", [])
        return {"dismissed": 0}

    def merge(self, merges):
        """Merge `remove` into `keep`; with `okay`, the group's other entries stay as they are."""
        tracks = {t["id"]: t for t in self.store.tracks()}
        groups = [g for g in self.groups(list(tracks.values())) if not g["merged"]]
        source = self.store.setting("last_scan_source")
        plan, used, rest = [], set(), []
        for merge in merges:
            ids = [merge["keep"], *merge["remove"]]
            group = next((g for g in groups if set(ids) <= set(g["tracks"])), None)
            if (
                len(ids) < 2
                or len(set(ids)) != len(ids)
                or used & set(ids)
                or group is None
                or set(ids) & set(group["awaiting_removal"])
            ):
                raise ValueError("Duplicate groups changed; refresh and review again")
            if any(tracks[i]["source"] != source for i in ids):
                raise ValueError(
                    "Only entries from the scanned rekordbox library merge"
                )
            used |= set(ids)
            if merge.get("okay"):
                rest.append(
                    set(group["tracks"])
                    - set(group["awaiting_removal"])
                    - set(merge["remove"])
                )
            plan.append(
                {
                    "keep": tracks[merge["keep"]]["source_id"],
                    "remove": [tracks[i]["source_id"] for i in merge["remove"]],
                }
            )
        if not plan:
            raise ValueError("Choose at least one duplicate group to merge")
        leftovers = [i for merge in plan for i in merge["remove"]]

        def mutate(staged):
            moved = rekordbox.merge_entries(staged, plan, FOLDER)
            with rekordbox.database(staged) as db:
                listed = rekordbox.playlist_state(db, FOLDER).get(REMOVAL, [])
            rekordbox.write_playlists(
                staged,
                {
                    "folder": FOLDER,
                    "playlists": [
                        {
                            "name": REMOVAL,
                            "tracks": [
                                *listed,
                                *(i for i in leftovers if i not in listed),
                            ],
                        }
                    ],
                },
            )
            return moved

        result = self.operations.library_change(
            "duplicates merged",
            f"Merged {len(leftovers)} duplicate entries into {len(plan)} kept entries",
            [i for merge in plan for i in (merge["keep"], *merge["remove"])],
            mutate,
        )
        if rest and result["manifest"]["library_status"] == "complete":
            self.okay(rest)
            self.store.log(
                "duplicates", f"Marked the rest of {len(rest)} merged groups as okay"
            )
        return result
