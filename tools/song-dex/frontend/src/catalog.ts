export type CatalogTrack = {
  id: number;
  source: string;
  metadata: Record<string, string | number>;
  my_tags: { id: string; name: string; category: string }[];
  my_tags_loaded: number;
  playlists: { name: string }[];
};
export type Filters = {
  tags: string[];
  tagMode: "all" | "any";
  tagState: string;
  genres: string[];
  keys: string[];
  formats: string[];
  playlists: string[];
  bpmMin: string;
  bpmMax: string;
  yearMin: string;
  yearMax: string;
};
export const emptyFilters: Filters = {
  tags: [],
  tagMode: "all",
  tagState: "all",
  genres: [],
  keys: [],
  formats: [],
  playlists: [],
  bpmMin: "",
  bpmMax: "",
  yearMin: "",
  yearMax: "",
};
export const tagKey = (track: CatalogTrack, tag: { id: string }) =>
  `${track.source}::${tag.id}`;
export const tagName = (tag: { name: string; category: string }) =>
  [tag.category, tag.name].filter(Boolean).join(" / ");
const numeric = (value: unknown) => {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
};
export function matchesFilters(track: CatalogTrack, f: Filters): boolean {
  const m = track.metadata;
  for (const [field, min, max] of [
    ["bpm", f.bpmMin, f.bpmMax],
    ["year", f.yearMin, f.yearMax],
  ]) {
    if (min !== "" || max !== "") {
      const n = numeric(m[field]);
      if (
        n === null ||
        (min !== "" && n < Number(min)) ||
        (max !== "" && n > Number(max))
      )
        return false;
    }
  }
  for (const [field, chosen] of [
    ["genre", f.genres],
    ["key", f.keys],
    ["format", f.formats],
  ] as const)
    if (chosen.length && !chosen.includes(String(m[field] ?? "").trim()))
      return false;
  if (
    f.playlists.length &&
    !track.playlists.some((p) => f.playlists.includes(p.name))
  )
    return false;
  const tags = track.my_tags.map((tag) => tagKey(track, tag));
  if (
    f.tags.length &&
    !(f.tagMode === "all"
      ? f.tags.every((t) => tags.includes(t))
      : f.tags.some((t) => tags.includes(t)))
  )
    return false;
  if (f.tagState === "tagged" && !tags.length) return false;
  if (f.tagState === "untagged" && (!track.my_tags_loaded || tags.length))
    return false;
  if (f.tagState === "unknown" && track.my_tags_loaded) return false;
  return true;
}
export function compareTracks(
  a: CatalogTrack,
  b: CatalogTrack,
  field: string,
  direction: string,
): number {
  const ascending = direction === "asc" ? 1 : -1;
  let av: string | number | null, bv: string | number | null;
  if (field === "dex") {
    av = a.id;
    bv = b.id;
  } else if (["bpm", "year", "duration"].includes(field)) {
    av = numeric(a.metadata[field]);
    bv = numeric(b.metadata[field]);
  } else if (field === "my_tags") {
    av = a.my_tags.map(tagName).sort().join(", ") || null;
    bv = b.my_tags.map(tagName).sort().join(", ") || null;
  } else {
    av = String(a.metadata[field] ?? "").trim() || null;
    bv = String(b.metadata[field] ?? "").trim() || null;
  }
  if (av === null || bv === null)
    return av === bv ? a.id - b.id : av === null ? 1 : -1;
  const compared =
    typeof av === "number" && typeof bv === "number"
      ? av - bv
      : String(av).localeCompare(String(bv), undefined, {
          numeric: true,
          sensitivity: "base",
        });
  return compared * ascending || a.id - b.id;
}
export function activeFilterCount(f: Filters): number {
  return (
    f.tags.length +
    f.genres.length +
    f.keys.length +
    f.formats.length +
    f.playlists.length +
    [f.bpmMin, f.bpmMax, f.yearMin, f.yearMax].filter(Boolean).length +
    (f.tagState === "all" ? 0 : 1)
  );
}
