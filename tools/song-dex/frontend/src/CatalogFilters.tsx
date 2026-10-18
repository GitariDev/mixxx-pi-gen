import { useId, useMemo, useRef, useState } from "react";
import {
  activeFilterCount,
  addedDay,
  emptyFilters,
  tagKey,
  tagName,
} from "./catalog";
import type { CatalogTrack, Filters } from "./catalog";
import { closeness, fold } from "./GenreInput";

type Option = { id: string; name: string; count: number };
type ListKey =
  | "tags"
  | "genres"
  | "artists"
  | "albums"
  | "labels"
  | "keys"
  | "formats"
  | "playlists";

/** Values to pick as you type: the collection's own, closest and most used first. */
function ValuePicker({
  label,
  options,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  options: Option[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
}) {
  const id = useId(),
    input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState(""),
    [open, setOpen] = useState(false),
    [active, setActive] = useState(-1);
  const names = useMemo(
    () => new Map(options.map((o) => [o.id, o.name])),
    [options],
  );
  const matches = useMemo(() => {
    const query = fold(text),
      left = options.filter((o) => !value.includes(o.id));
    if (!query) return [...left].sort((a, b) => b.count - a.count).slice(0, 8);
    const found: (Option & { score: number })[] = [];
    for (const o of left) {
      const score = closeness(query, fold(o.name));
      if (score !== null) found.push({ ...o, score });
    }
    return found
      .sort((a, b) => a.score - b.score || b.count - a.count)
      .slice(0, 8);
  }, [options, value, text]);
  const add = (o: Option) => {
    onChange([...value, o.id]);
    setText("");
    setActive(-1);
  };
  const shown = open && (matches.length > 0 || !!text.trim());
  return (
    <div
      className="value-picker"
      onMouseDown={(e) => {
        // A click on the box (not a chip) types into it.
        if (e.target === e.currentTarget) {
          e.preventDefault();
          input.current?.focus();
        }
      }}
    >
      {value.map((v) => (
        <span className="value-chip" key={v}>
          {names.get(v) ?? "Not in this collection"}
          <button
            type="button"
            aria-label={`Remove ${names.get(v) ?? v} from ${label}`}
            onClick={() => onChange(value.filter((x) => x !== v))}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={input}
        role="combobox"
        aria-label={label}
        aria-expanded={shown}
        aria-controls={id}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${id}-${active}` : undefined}
        autoComplete="off"
        placeholder={value.length ? "Add another…" : placeholder}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(e.target.value.trim() ? 0 : -1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          setOpen(false);
          setActive(-1);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            if (matches.length)
              setActive(
                (active + (e.key === "ArrowDown" ? 1 : -1) + matches.length) %
                  matches.length,
              );
          } else if (e.key === "Enter" && shown && matches[active]) {
            e.preventDefault();
            add(matches[active]);
          } else if (e.key === "Backspace" && !text && value.length) {
            onChange(value.slice(0, -1));
          } else if (e.key === "Escape" && shown) {
            e.stopPropagation();
            setOpen(false);
          }
        }}
      />
      {shown && (
        <ul className="genre-options" role="listbox" id={id}>
          {matches.map((o, i) => (
            <li
              key={o.id}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : undefined}
              // Keep focus in the input so several values can be added in a row.
              onMouseDown={(e) => {
                e.preventDefault();
                add(o);
              }}
            >
              <span>{o.name}</span>
              <small>
                {o.count.toLocaleString()} {o.count === 1 ? "track" : "tracks"}
              </small>
            </li>
          ))}
          {!matches.length && (
            <li className="no-match" aria-disabled>
              {options.length
                ? `No ${label.toLowerCase()} match “${text.trim()}”`
                : `No ${label.toLowerCase()} in this collection`}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/** A from–to pair; either end may stay open. */
function Range({
  label,
  from,
  to,
  onChange,
  type = "number",
  step,
  hint,
  list,
}: {
  label: string;
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
  type?: "number" | "date";
  step?: string;
  hint?: [string, string];
  list?: string;
}) {
  return (
    <div className="range-pair">
      <input
        type={type}
        inputMode={type === "number" ? "decimal" : undefined}
        min={type === "number" ? "0" : hint?.[0]}
        max={type === "date" ? hint?.[1] : undefined}
        step={step}
        list={list}
        aria-label={`${label} from`}
        placeholder={hint ? `From ${hint[0]}` : "From"}
        value={from}
        onChange={(e) => onChange(e.target.value, to)}
      />
      <span aria-hidden="true">to</span>
      <input
        type={type}
        inputMode={type === "number" ? "decimal" : undefined}
        min={type === "number" ? "0" : hint?.[0]}
        max={type === "date" ? hint?.[1] : undefined}
        step={step}
        list={list}
        aria-label={`${label} to`}
        placeholder={hint ? `To ${hint[1]}` : "To"}
        value={to}
        onChange={(e) => onChange(from, e.target.value)}
      />
    </div>
  );
}

const day = (d: Date) => d.toLocaleDateString("en-CA");
const daysAgo = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return day(d);
};
const presets: [string, () => string][] = [
  ["Last 7 days", () => daysAgo(7)],
  ["Last 30 days", () => daysAgo(30)],
  ["Last 90 days", () => daysAgo(90)],
  ["This year", () => `${new Date().getFullYear()}-01-01`],
];
const tagStates: [string, string][] = [
  ["all", "Either"],
  ["tagged", "With My Tags"],
  ["untagged", "Without My Tags"],
  ["unknown", "Not loaded yet"],
];

export function CatalogFilters({
  tracks,
  value,
  onChange,
  onLoadTags,
  busy,
  defaultOpen = false,
}: {
  tracks: CatalogTrack[];
  value: Filters;
  onChange: (f: Filters) => void;
  onLoadTags: () => void;
  busy: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const uid = useId();
  const library = useMemo(() => {
    const counted = (values: (t: CatalogTrack) => [string, string][]) => {
      const found = new Map<string, Option>();
      for (const t of tracks)
        for (const [id, name] of new Map(values(t)))
          if (id) {
            const prior = found.get(id);
            found.set(id, { id, name, count: (prior?.count ?? 0) + 1 });
          }
      return [...found.values()].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { numeric: true }),
      );
    };
    const field = (name: string) =>
      counted((t) => {
        const v = String(t.metadata[name] ?? "").trim();
        return [[v, v]];
      });
    const numbers = (name: string) =>
      tracks.map((t) => Number(t.metadata[name])).filter((n) => n > 0);
    const bpms = numbers("bpm"),
      years = numbers("year"),
      days = tracks.map(addedDay).filter(Boolean).sort();
    return {
      tags: counted((t) => t.my_tags.map((g) => [tagKey(t, g), tagName(g)])),
      playlists: counted((t) => t.playlists.map((p) => [p.name, p.name])),
      genres: field("genre"),
      artists: field("artist"),
      albums: field("album"),
      labels: field("label"),
      keys: field("key"),
      formats: field("format"),
      bpm: bpms.length
        ? ([Math.floor(Math.min(...bpms)), Math.ceil(Math.max(...bpms))].map(
            String,
          ) as [string, string])
        : undefined,
      year: years.length
        ? ([Math.min(...years), Math.max(...years)].map(String) as [
            string,
            string,
          ])
        : undefined,
      years: [...new Set(years)].sort((a, b) => b - a),
      added: days.length
        ? ([days[0], days[days.length - 1]] as [string, string])
        : undefined,
    };
  }, [tracks]);
  const count = activeFilterCount(value);
  const update = (f: Partial<Filters>) => onChange({ ...value, ...f });
  const invalid =
    (value.bpmMin &&
      value.bpmMax &&
      Number(value.bpmMin) > Number(value.bpmMax)) ||
    (value.yearMin &&
      value.yearMax &&
      Number(value.yearMin) > Number(value.yearMax)) ||
    (value.addedFrom && value.addedTo && value.addedFrom > value.addedTo);
  const picker = (key: ListKey, label: string, placeholder: string) => (
    <div className="filter-row">
      <span className="filter-label">{label}</span>
      <ValuePicker
        label={label}
        options={library[key]}
        value={value[key]}
        onChange={(v) => update({ [key]: v })}
        placeholder={placeholder}
      />
    </div>
  );
  // What is filtering, readable and removable while the panel is closed.
  const names = (key: ListKey) =>
    new Map(library[key].map((o) => [o.id, o.name]));
  const chips: { key: string; text: string; clear: Partial<Filters> }[] = [];
  for (const [key, label] of [
    ["tags", "My Tag"],
    ["playlists", "Playlist"],
    ["genres", "Genre"],
    ["artists", "Artist"],
    ["albums", "Album"],
    ["labels", "Label"],
    ["keys", "Key"],
    ["formats", "Format"],
  ] as [ListKey, string][]) {
    const known = names(key);
    for (const v of value[key])
      chips.push({
        key: key + v,
        text: `${label}: ${known.get(v) ?? "not in this collection"}`,
        clear: { [key]: value[key].filter((x) => x !== v) },
      });
  }
  for (const [label, from, to, clear] of [
    ["BPM", value.bpmMin, value.bpmMax, { bpmMin: "", bpmMax: "" }],
    ["Year", value.yearMin, value.yearMax, { yearMin: "", yearMax: "" }],
    ["Added", value.addedFrom, value.addedTo, { addedFrom: "", addedTo: "" }],
  ] as [string, string, string, Partial<Filters>][])
    if (from || to)
      chips.push({
        key: label,
        text: `${label}: ${from && to ? `${from} – ${to}` : from ? `from ${from}` : `up to ${to}`}`,
        clear,
      });
  if (value.tagState !== "all")
    chips.push({
      key: "state",
      text: tagStates.find(([v]) => v === value.tagState)?.[1] ?? "",
      clear: { tagState: "all" },
    });
  return (
    <section className="catalog-filters" aria-label="Filter music">
      <header>
        <button
          type="button"
          className="filter-toggle"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <span aria-hidden="true">{open ? "▾" : "▸"}</span> Filters
          {count > 0 && <b>{count}</b>}
        </button>
        {!open && !count && (
          <span className="filter-teaser">
            My Tags · genre · artist · BPM · date added…
          </span>
        )}
        {count > 0 && (
          <button
            type="button"
            className="quiet"
            onClick={() => onChange({ ...emptyFilters })}
          >
            Clear all
          </button>
        )}
      </header>
      {chips.length > 0 && (
        <div className="filter-active">
          {chips.map((c) => (
            <button
              type="button"
              key={c.key}
              aria-label={`Remove filter ${c.text}`}
              onClick={() => update(c.clear)}
            >
              {c.text} <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      )}
      {open && (
        <div className="filter-body">
          <p className="filter-hint">
            Type to pick from what is in your library. Several values in one row
            match <strong>any</strong> of them; tracks must match{" "}
            <strong>every</strong> row you fill in.
          </p>
          <fieldset>
            <legend>Tags & playlists</legend>
            {picker("tags", "My Tags", "Type a My Tag…")}
            <div className="filter-row">
              <span className="filter-label" id={`${uid}-state`}>
                Tagged?
              </span>
              <div
                className="segmented"
                role="group"
                aria-labelledby={`${uid}-state`}
              >
                {tagStates
                  .filter(
                    ([v]) =>
                      v !== "unknown" ||
                      value.tagState === v ||
                      tracks.some((t) => !t.my_tags_loaded),
                  )
                  .map(([v, text]) => (
                    <button
                      type="button"
                      key={v}
                      aria-pressed={value.tagState === v}
                      onClick={() => update({ tagState: v })}
                    >
                      {text}
                    </button>
                  ))}
              </div>
            </div>
            {picker("playlists", "Playlists", "Type a playlist…")}
          </fieldset>
          <fieldset>
            <legend>Track details</legend>
            {picker("genres", "Genre", "Type a genre…")}
            {picker("artists", "Artist", "Type an artist…")}
            {picker("albums", "Album", "Type an album…")}
            {picker("labels", "Label", "Type a label…")}
            {picker("keys", "Key", "Type a key, e.g. 8A…")}
            {picker("formats", "Format", "MP3, FLAC…")}
          </fieldset>
          <fieldset>
            <legend>Ranges</legend>
            <div className="filter-row">
              <span className="filter-label">BPM</span>
              <Range
                label="BPM"
                step="0.01"
                hint={library.bpm}
                from={value.bpmMin}
                to={value.bpmMax}
                onChange={(bpmMin, bpmMax) => update({ bpmMin, bpmMax })}
              />
            </div>
            <div className="filter-row">
              <span className="filter-label">Year</span>
              <Range
                label="Year"
                step="1"
                hint={library.year}
                list={uid}
                from={value.yearMin}
                to={value.yearMax}
                onChange={(yearMin, yearMax) => update({ yearMin, yearMax })}
              />
              <datalist id={uid}>
                {library.years.map((y) => (
                  <option key={y} value={y} />
                ))}
              </datalist>
            </div>
            <div className="filter-row">
              <span className="filter-label">Date added</span>
              <div>
                <Range
                  label="Date added"
                  type="date"
                  hint={library.added}
                  from={value.addedFrom}
                  to={value.addedTo}
                  onChange={(addedFrom, addedTo) =>
                    update({ addedFrom, addedTo })
                  }
                />
                <div className="range-presets">
                  {presets.map(([text, from]) => (
                    <button
                      type="button"
                      key={text}
                      aria-pressed={
                        value.addedFrom === from() && !value.addedTo
                      }
                      onClick={() => update({ addedFrom: from(), addedTo: "" })}
                    >
                      {text}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </fieldset>
          {invalid && (
            <p role="alert" className="error-text">
              A range starts after it ends. Swap the values to see results.
            </p>
          )}
          <p className="fine">
            An open end includes everything past it; tracks with no value are
            left out of a range. Date added is the day rekordbox added the
            track.
          </p>
          {tracks.some(
            (t) =>
              t.source !== "local" && t.source !== "demo" && !t.my_tags_loaded,
          ) && (
            <p className="fine">
              Some My Tags have not been imported.{" "}
              <button type="button" disabled={busy} onClick={onLoadTags}>
                Load My Tags from last scan
              </button>
            </p>
          )}
        </div>
      )}
    </section>
  );
}
