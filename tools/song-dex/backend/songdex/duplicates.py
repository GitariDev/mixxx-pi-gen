"""Actionable duplicates: suggest the entry to keep and merge the others into it.

A merge moves playlist places and My Tags to the kept entry and lists the leftover
entries in one rekordbox playlist. Removing them from the collection stays a
rekordbox action; Song Dex never deletes collection rows or files.

Marking a group as okay records the entries that stay separate, such as remixes
and other versions. Entries merged out of the group keep waiting for removal.

Larger groups are checked a second time and split into versions, so copies of one
version can merge while the versions themselves stay apart.
"""

from __future__ import annotations

import re

from . import rekordbox
from .providers import normalized, version_signature, version_tokens

FOLDER, REMOVAL = "Song Dex", "Duplicates to remove"
LOSSLESS = {"FLAC", "WAV", "AIFF", "AIF"}
# Open entries a group needs before it is split into versions; a trio can hold a pair.
VERSIONS_FROM = 3
GENERIC = {"", "original", "original mix", "original version"}
FRAGMENT = r"\(([^)]*)\)|\[([^]]*)\]"
ORIGINAL = r"[(\[]\s*original(?: mix| version)?\s*[)\]]"


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


def merged(track):
    return {**track["metadata"], **track["accepted"]}


def number(m, field):
    return float(m.get(field) or 0)


def same_version(a, b):
    """One recording: same version labels, duration within 1% and BPM within 1."""
    ma, mb = merged(a), merged(b)
    if version_signature(ma.get("title", ""), ma.get("version", "")) != (
        version_signature(mb.get("title", ""), mb.get("version", ""))
    ):
        return False
    da, db = number(ma, "duration"), number(mb, "duration")
    if abs(da - db) > max(2, max(da, db) * 0.01):
        return False
    ba, bb = number(ma, "bpm"), number(mb, "bpm")
    return not (ba and bb and abs(ba - bb) > 1)


def capitalized(text):
    return " ".join(w[:1].upper() + w[1:] for w in text.split())


def version_label(track):
    """The version qualifiers as written ("Extended Mix"), or "Original" without any."""
    m = merged(track)
    title, version = str(m.get("title") or ""), str(m.get("version") or "")
    parts = [a or b for a, b in re.findall(FRAGMENT, title) if version_tokens(a or b)]
    if normalized(version) not in GENERIC:
        parts.append(version)
    if not parts:
        # Qualifiers outside brackets, such as a title every entry shares.
        words = version_tokens(f"{title} {version}")
        parts = [w for w in normalized(f"{title} {version}").split() if w in words]
        parts = [" ".join(dict.fromkeys(parts))] if parts else []
    labels = {normalized(p): capitalized(p) for p in parts if p.strip()}
    return " / ".join(labels.values()) or "Original"


def plain_title(track):
    """The title without a generic "(Original Mix)", which names no other version."""
    return normalized(
        re.sub(ORIGINAL, "", str(merged(track).get("title") or ""), flags=re.I)
    )


def clock(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def versions(entries):
    """Cluster a group's open entries into versions, or None when there is nothing to pair."""
    clusters = []
    for t in entries:
        home = next(
            (
                c
                for c in clusters
                if t.get("file_hash")
                and any(o.get("file_hash") == t["file_hash"] for o in c)
            ),
            None,
        ) or next((c for c in clusters if same_version(c[0], t)), None)
        if home:
            home.append(t)
        else:
            clusters.append([t])
    if len(clusters) < 2 or all(len(c) < 2 for c in clusters):
        return None
    # Copies to merge lead, larger first; single versions follow in group order.
    clusters.sort(key=len, reverse=True)
    keeps = [max(c, key=strength) for c in clusters]
    labels = [version_label(k) for k in keeps]
    found = []
    for c, keep, label in zip(clusters, keeps, labels):
        if labels.count(label) > 1:
            label = f"{label} · {clock(number(merged(keep), 'duration'))}"
        hashes = {t.get("file_hash") for t in c}
        found.append(
            {
                "label": label,
                "tracks": [t["id"] for t in c],
                "keep": keep["id"],
                "warnings": ["Titles differ beyond punctuation"]
                if len({plain_title(t) for t in c}) > 1
                else [],
                "same_file": len(c) > 1 and len(hashes) == 1 and None not in hashes,
            }
        )
    return found


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
            closed = okayed or len(open_ids) < 2
            found = None
            if not closed and len(open_ids) >= VERSIONS_FROM:
                found = versions([by_id[i] for i in open_ids])
            entry = {
                **group,
                "keep": max(open_ids or ids, key=lambda i: strength(by_id[i])),
                "awaiting_removal": waiting,
                "merged": closed,
            }
            if found:
                # Entries follow their versions; those waiting for removal come last.
                entry["versions"] = found
                entry["tracks"] = [*(i for v in found for i in v["tracks"]), *waiting]
            groups.append(entry)
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
        plan, used, okayed = [], set(), {}
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
                okayed[frozenset(group["tracks"])] = group
            plan.append(
                {
                    "keep": tracks[merge["keep"]]["source_id"],
                    "remove": [tracks[i]["source_id"] for i in merge["remove"]],
                }
            )
        if not plan:
            raise ValueError("Choose at least one duplicate group to merge")
        leftovers = [i for merge in plan for i in merge["remove"]]
        # Several merges in one group, one per version, leave one set of entries okay.
        removed = {i for merge in merges for i in merge["remove"]}
        rest = [
            set(g["tracks"]) - set(g["awaiting_removal"]) - removed
            for g in okayed.values()
        ]

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
