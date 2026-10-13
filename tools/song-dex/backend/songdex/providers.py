from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import httpx

from .db import cosmetic, dump, now

UPPER = {"r&b", "uk", "us", "edm", "idm", "dj", "mpb"}
SMALL = {"and", "of", "the", "n"}


def normalized(value):
    return " ".join(
        re.sub(
            r"[^\w\s]", " ", unicodedata.normalize("NFKC", str(value)).casefold()
        ).split()
    )


def version_tokens(title):
    words = normalized(title)
    return frozenset(
        re.findall(
            r"\b(?:remix|extended|radio|edit|live|acoustic|instrumental|clean|explicit|remaster|bootleg|vip)\b",
            words,
        )
    )


def version_signature(title, version=""):
    # Retain the identity of the remixer/edit, not just the word 'remix'.
    explicit = normalized(version)
    generic_original = {"", "original", "original mix", "original version"}
    fragments = re.findall(r"\(([^)]*)\)|\[([^]]*)\]", title)
    qualifiers = {normalized(a or b) for a, b in fragments if version_tokens(a or b)}
    if explicit not in generic_original:
        qualifiers.add(explicit)
    words = version_tokens(title + " " + version)
    return words, frozenset(qualifiers)


def genre_name(name):
    """MusicBrainz genres are lower case; present them like a tag ("Hip Hop", "R&B")."""
    words = [
        w.upper() if w in UPPER else w if w in SMALL and i else w.capitalize()
        for i, w in enumerate(str(name).split())
    ]
    return " ".join(words)


def top_genre(genres, known=()):
    """The best-supported genre, preferring one the collection already uses."""
    ranked = sorted(genres or [], key=lambda g: (-g.get("count", 0), g.get("name", "")))
    if not ranked:
        return None
    strong = [g for g in ranked if g.get("count", 0) * 3 >= ranked[0].get("count", 0)]
    familiar = [g for g in strong if cosmetic(g.get("name")) in known]
    return (familiar or ranked)[0].get("name")


DISCOGS_PAGE = "https://www.discogs.com"
DISCOGS_KEEP = timedelta(hours=6)


def discogs_auth(store):
    """Authorization header from a personal access token, or an application's key and secret."""
    token = store.setting("discogs_token", "")
    key, secret = store.setting("discogs_key", ""), store.setting("discogs_secret", "")
    if token:
        return f"Discogs token={token}"
    if key and secret:
        return f"Discogs key={key}, secret={secret}"
    return ""


def main_artist(credited):
    return re.split(
        r"\s+(?:feat\.?|ft\.?|featuring|x|&|and)\s+|,", str(credited), flags=re.I
    )[0].strip()


def loose(value):
    return cosmetic(value).replace(" ", "")


def lucene(value):
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", str(value))


def split_name(title):
    """Artist, title and album from a file-name style title such as "Artist - Title".

    Returns None unless the shape is clear; "Title - Someone Remix" is left alone.
    """
    parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", str(title)) if p.strip()]
    album = ""
    if len(parts) == 3 and re.match(r"\d{1,2}[\s.]+\S", parts[2]):
        album, parts = parts[1], [parts[0], re.sub(r"^\d{1,2}[\s.]+", "", parts[2])]
    if len(parts) != 2:
        return None
    outside = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", parts[1])
    if version_tokens(outside) or parts[0].isdigit():
        return None
    return {
        "artist": parts[0],
        "title": parts[1],
        **({"album": album} if album else {}),
    }


def artist_credit(record):
    return "".join(
        (a.get("name") or a.get("artist", {}).get("name", "")) + a.get("joinphrase", "")
        for a in record.get("artist-credit", [])
    )


class Providers:
    def __init__(self, store):
        self.store = store
        self.last_request = 0.0

    def get(self, url, params, headers=None, keep=timedelta(days=30)):
        key = url + dump(params)
        with self.store.connect() as db:
            row = db.execute(
                "SELECT value,created_at FROM cache WHERE key=?", (key,)
            ).fetchone()
        if (
            row
            and datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"])
            < keep
        ):
            return json.loads(row["value"])
        time.sleep(max(0, 1.1 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        with httpx.Client(
            timeout=20,
            headers={
                "User-Agent": "SongDex/0.1 (personal local music catalog)",
                **(headers or {}),
            },
        ) as client:
            for pause in (3, 8, None):
                response = client.get(url, params=params)
                # 503 (MusicBrainz busy) or 429 (rate limit reached): wait and ask again.
                if response.status_code not in (429, 503) or pause is None:
                    break
                time.sleep(pause)
                self.last_request = time.monotonic()
            response.raise_for_status()
            data = response.json()
        with self.store.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key, dump(data), now())
            )
        return data

    def fingerprint_ids(self, track):
        key = self.store.setting("acoustid_key", "")
        binary = shutil.which("fpcalc")
        if not key or not binary or not track["available"]:
            return set(), []
        result = subprocess.run(
            [binary, "-json", track["path"]],
            capture_output=True,
            text=True,
            timeout=90,
            check=True,
        )
        fp = json.loads(result.stdout)
        result = self.get(
            "https://api.acoustid.org/v2/lookup",
            {
                "client": key,
                "duration": round(fp["duration"]),
                "fingerprint": fp["fingerprint"],
                "meta": "recordings",
            },
        )
        ids = {
            r["id"]
            for hit in result.get("results", [])
            if hit.get("score", 0) >= 0.95
            for r in hit.get("recordings", [])
        }
        return ids, [
            {
                "provider": "AcoustID",
                "reason": "Audio fingerprint candidates; versions still require comparison",
                "recording_ids": sorted(ids),
            }
        ]

    def enrich(self, track):
        m = track["metadata"]
        named = None if m.get("artist") else split_name(m.get("title", ""))
        if named:
            for field, value in named.items():
                if field != "album" or not m.get("album"):
                    self.store.propose(
                        track,
                        field,
                        value,
                        "review",
                        "From the track's name; it has no artist tag",
                        "name",
                    )
            # Look the track up as the name describes it.
            track = {**track, "metadata": {**m, **named}}
        evidence = self.match(track)
        if cosmetic(m.get("genre", "")) in ("", "unknown genre", "other"):
            with self.store.connect() as db:
                found = db.execute(
                    "SELECT 1 FROM proposals WHERE track_id=? AND field='genre' AND status='pending'",
                    (track["id"],),
                ).fetchone()
            if not found:
                try:
                    self.discogs_genre(track) or self.artist_genre(track)
                except httpx.HTTPError:
                    pass
        return evidence

    def match(self, track):
        m = track["metadata"]
        evidence, ids = [], set()
        try:
            ids, fp_evidence = self.fingerprint_ids(track)
            evidence.extend(fp_evidence)
        except Exception:
            evidence.append(
                {
                    "provider": "AcoustID",
                    "error": "Fingerprint lookup unavailable; catalog matching still runs",
                }
            )
        if not m.get("title") and not ids:
            return evidence + [
                {
                    "provider": "MusicBrainz",
                    "error": "No title or audio fingerprint available",
                }
            ]
        if ids:
            candidates = [
                self.get(
                    f"https://musicbrainz.org/ws/2/recording/{rid}",
                    {"fmt": "json", "inc": "artist-credits+releases+isrcs+genres"},
                )
                for rid in sorted(ids)[:5]
            ]
        else:
            query = f'recording:"{lucene(m.get("title", ""))}"'
            if m.get("artist"):
                query += f' AND artist:"{lucene(m["artist"])}"'
            candidates = self.get(
                "https://musicbrainz.org/ws/2/recording",
                {"query": query, "fmt": "json", "limit": 8},
            ).get("recordings", [])
        ranked = []
        for c in candidates:
            name = artist_credit(c)
            ts = SequenceMatcher(
                None, normalized(m.get("title", "")), normalized(c.get("title", ""))
            ).ratio()
            ars = SequenceMatcher(
                None, normalized(m.get("artist", "")), normalized(name)
            ).ratio()
            duration = c.get("length", 0) / 1000
            delta = (
                abs(float(m.get("duration", 0)) - duration)
                if duration and m.get("duration")
                else None
            )
            conflict = version_signature(
                m.get("title", ""), m.get("version", "")
            ) != version_signature(c.get("title", ""), c.get("disambiguation", ""))
            score = (
                ts * 0.45
                + ars * 0.35
                + (0.2 if delta is not None and delta <= 2 else 0)
            )
            ranked.append((score, c, delta, conflict, ts, ars))
        ranked.sort(key=lambda r: r[0], reverse=True)
        for score, c, delta, conflict, _, _ in ranked:
            evidence.append(
                {
                    "provider": "MusicBrainz",
                    "title": c.get("title"),
                    "artist": artist_credit(c),
                    "url": "https://musicbrainz.org/recording/" + c["id"],
                    "recording_id": c["id"],
                    "duration_difference": delta,
                    "version_conflict": conflict,
                    "reason": "Version differs"
                    if conflict
                    else "Recording candidate; release identity evaluated separately",
                }
            )
        if not ranked:
            return evidence + [
                {
                    "provider": "MusicBrainz",
                    "reason": "No candidates found; existing values preserved",
                }
            ]
        score, candidate, delta, conflict, ts, ars = ranked[0]
        unique = len(ranked) == 1 or score - ranked[1][0] >= 0.1
        fingerprint_unique = len(ids) == 1 and candidate["id"] in ids
        high = (
            unique
            and not conflict
            and delta is not None
            and delta <= 2
            and ((ts == 1 and ars == 1) or fingerprint_unique)
        )
        if conflict or score < 0.60:
            return evidence
        confidence = "high" if high else "review"
        source = "https://musicbrainz.org/recording/" + candidate["id"]
        reason = (
            "Unique recording, matching version and duration"
            if high
            else "Possible match; confirm the recording before accepting"
        )
        for field, value in [
            ("title", candidate.get("title")),
            ("artist", artist_credit(candidate)),
        ]:
            self.store.propose(track, field, value, confidence, reason, source)
        # Never assign a compilation/reissue merely because it contains this recording.
        releases = [
            r
            for r in candidate.get("releases", [])
            if normalized(r.get("title", "")) == normalized(m.get("album", ""))
            and m.get("album")
        ]
        if high and len(releases) == 1:
            release = self.get(
                "https://musicbrainz.org/ws/2/release/" + releases[0]["id"],
                {"fmt": "json", "inc": "artist-credits+labels"},
            )
            release_source = "https://musicbrainz.org/release/" + release["id"]
            for field, value in [
                ("album", release.get("title")),
                ("album_artist", artist_credit(release)),
                ("year", release.get("date", "")[:4]),
            ]:
                self.store.propose(
                    track,
                    field,
                    value,
                    "review",
                    "Album name matches; confirm the release edition",
                    release_source,
                )
            labels = {
                info.get("label", {}).get("name")
                for info in release.get("label-info", [])
            } - {None}
            if len(labels) == 1:
                self.store.propose(
                    track,
                    "label",
                    next(iter(labels)),
                    "review",
                    "Label from candidate release",
                    release_source,
                )
        if cosmetic(m.get("genre", "")) in ("", "unknown genre", "other"):
            self.suggest_genre(track, candidate, source)
        return evidence

    def library_genres(self):
        """The collection's own spelling for each genre, most used first."""
        if time.monotonic() - getattr(self, "_genres_at", -1e9) > 300:
            spellings = {}
            for t in self.store.tracks():
                name = {**t["metadata"], **t["accepted"]}.get("genre")
                if name:
                    counts = spellings.setdefault(cosmetic(name), {})
                    counts[name] = counts.get(name, 0) + 1
            self._genres = {k: max(v, key=v.get) for k, v in spellings.items()}
            self._genres_at = time.monotonic()
        return self._genres

    def discogs_genre(self, track):
        """Style or genre of a Discogs release carrying this artist and track, when a token is set.

        Discogs' terms: responses are kept at most six hours, and every use of the
        data is shown with a "Data provided by Discogs" link to its page.
        """
        auth = discogs_auth(self.store)
        m = track["metadata"]
        artist = main_artist(m.get("artist", ""))
        title = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", m.get("title", "")).strip()
        if not auth or not artist or not title:
            return False
        results = self.get(
            "https://api.discogs.com/database/search",
            {"type": "release", "artist": artist, "track": title, "per_page": 5},
            headers={"Authorization": auth},
            keep=DISCOGS_KEEP,
        ).get("results", [])
        for result in results:
            # Result titles read "Artist - Release".
            if loose(artist) not in loose(result.get("title", "").split(" - ")[0]):
                continue
            known = self.library_genres()
            names = [*(result.get("style") or []), *(result.get("genre") or [])]
            familiar = [n for n in names if cosmetic(n) in known]
            if not names or not result.get("uri"):
                continue
            name = (familiar or names)[0]
            self.store.propose(
                track,
                "genre",
                known.get(cosmetic(name), name),
                "review",
                f"Style of the release “{result.get('title', '')}”; this track may differ",
                DISCOGS_PAGE + result["uri"],
            )
            return True
        return False

    def artist_genre(self, track):
        """Fallback when no recording matched: the genre of an unambiguous artist."""
        name = main_artist(track["metadata"].get("artist", ""))
        if not name:
            return
        found = self.get(
            "https://musicbrainz.org/ws/2/artist",
            {"query": f'artist:"{lucene(name)}"', "fmt": "json", "limit": 5},
        ).get("artists", [])
        same = [
            a
            for a in found
            if loose(name)
            in {
                loose(a.get("name", "")),
                *(loose(x.get("name", "")) for x in a.get("aliases") or []),
            }
        ]
        # Several artists share many names; borrow a genre only from a single match.
        if len(same) != 1:
            return
        detail = self.get(
            "https://musicbrainz.org/ws/2/artist/" + same[0]["id"],
            {"fmt": "json", "inc": "genres"},
        )
        genre = top_genre(detail.get("genres"), self.library_genres())
        if genre:
            self.store.propose(
                track,
                "genre",
                self.library_genres().get(cosmetic(genre), genre_name(genre)),
                "review",
                f"Community genre for {same[0]['name']}; this track may differ",
                "https://musicbrainz.org/artist/" + same[0]["id"],
            )

    def suggest_genre(self, track, candidate, source):
        """Fill an empty genre from the recording's community genre, else its main artist's."""
        m = track["metadata"]
        credit = candidate.get("artist-credit") or [{}]
        main = credit[0].get("name") or credit[0].get("artist", {}).get("name", "")
        # A genre borrowed from an artist is only as good as the artist match.
        if not main or loose(main) not in loose(m.get("artist", "")):
            return
        detail = self.get(
            f"https://musicbrainz.org/ws/2/recording/{candidate['id']}",
            {"fmt": "json", "inc": "genres+artist-credits"},
        )
        artists = detail.get("artist-credit") or [{}]
        for genres, reason in (
            (detail.get("genres"), "Community genre for this recording"),
            (
                artists[0].get("artist", {}).get("genres"),
                f"Community genre for {main}; this track may differ",
            ),
        ):
            name = top_genre(genres, self.library_genres())
            if name:
                self.store.propose(
                    track,
                    "genre",
                    self.library_genres().get(cosmetic(name), genre_name(name)),
                    "review",
                    reason,
                    source,
                )
                return
