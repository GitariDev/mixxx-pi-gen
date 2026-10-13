import { useState } from "react";
import { activeFilterCount, emptyFilters, tagKey, tagName } from "./catalog";
import type { CatalogTrack, Filters } from "./catalog";
function Choices({
  title,
  options,
  value,
  onChange,
}: {
  title: string;
  options: { id: string; name: string; count: number }[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const [search, setSearch] = useState("");
  return (
    <details className="filter-choice">
      <summary>
        {title} <span>{value.length ? `${value.length} selected` : "Any"}</span>
      </summary>
      <input
        aria-label={`Search ${title}`}
        placeholder={`Search ${title.toLowerCase()}…`}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="filter-options">
        {options
          .filter((o) =>
            o.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
          )
          .map((o) => (
            <label key={o.id}>
              <input
                type="checkbox"
                checked={value.includes(o.id)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...value, o.id]
                      : value.filter((v) => v !== o.id),
                  )
                }
              />
              <span>{o.name}</span>
              <small>{o.count}</small>
            </label>
          ))}
        {!options.length && (
          <p className="fine">No values in this collection.</p>
        )}
      </div>
      {value.length > 0 && (
        <button type="button" onClick={() => onChange([])}>
          Clear {title.toLowerCase()}
        </button>
      )}
    </details>
  );
}
export function CatalogFilters({
  tracks,
  value,
  onChange,
  onLoadTags,
  busy,
}: {
  tracks: CatalogTrack[];
  value: Filters;
  onChange: (f: Filters) => void;
  onLoadTags: () => void;
  busy: boolean;
}) {
  const options = (field: string) => {
    const counts = new Map<string, number>();
    tracks.forEach((t) => {
      const values =
        field === "playlists"
          ? t.playlists.map((p) => p.name)
          : [String(t.metadata[field] ?? "").trim()];
      new Set(values.filter(Boolean)).forEach((v) =>
        counts.set(v, (counts.get(v) || 0) + 1),
      );
    });
    return [...counts]
      .map(([id, count]) => ({ id, name: id, count }))
      .sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { numeric: true }),
      );
  };
  const tags = new Map<string, { id: string; name: string; count: number }>();
  tracks.forEach((t) =>
    new Map(t.my_tags.map((g) => [tagKey(t, g), g])).forEach((g, id) => {
      const prior = tags.get(id);
      tags.set(id, { id, name: tagName(g), count: (prior?.count || 0) + 1 });
    }),
  );
  const count = activeFilterCount(value);
  const update = (f: Partial<Filters>) => onChange({ ...value, ...f });
  const invalid =
    (value.bpmMin &&
      value.bpmMax &&
      Number(value.bpmMin) > Number(value.bpmMax)) ||
    (value.yearMin &&
      value.yearMax &&
      Number(value.yearMin) > Number(value.yearMax));
  return (
    <details className="catalog-filters">
      <summary>
        Filter music{" "}
        <span>{count ? `${count} active` : "Tags · BPM · key · year"}</span>
      </summary>
      <div className="filter-grid">
        <Choices
          title="My Tags"
          options={[...tags.values()].sort((a, b) =>
            a.name.localeCompare(b.name),
          )}
          value={value.tags}
          onChange={(tags) => update({ tags })}
        />
        <label>
          Match selected tags
          <select
            value={value.tagMode}
            onChange={(e) =>
              update({ tagMode: e.target.value as "all" | "any" })
            }
          >
            <option value="all">All selected tags</option>
            <option value="any">Any selected tag</option>
          </select>
        </label>
        <label>
          Tag status
          <select
            value={value.tagState}
            onChange={(e) => update({ tagState: e.target.value })}
          >
            <option value="all">Any tag status</option>
            <option value="tagged">Has My Tags</option>
            <option value="untagged">No My Tags (confirmed)</option>
            <option value="unknown">My Tags not loaded</option>
          </select>
        </label>
        <Choices
          title="Genres"
          options={options("genre")}
          value={value.genres}
          onChange={(genres) => update({ genres })}
        />
        <Choices
          title="Keys"
          options={options("key")}
          value={value.keys}
          onChange={(keys) => update({ keys })}
        />
        <Choices
          title="Formats"
          options={options("format")}
          value={value.formats}
          onChange={(formats) => update({ formats })}
        />
        <Choices
          title="Playlists"
          options={options("playlists")}
          value={value.playlists}
          onChange={(playlists) => update({ playlists })}
        />
        <fieldset className="filter-range">
          <legend>BPM range</legend>
          <label>
            Minimum BPM
            <input
              type="number"
              min="0"
              step="0.01"
              value={value.bpmMin}
              onChange={(e) => update({ bpmMin: e.target.value })}
            />
          </label>
          <label>
            Maximum BPM
            <input
              type="number"
              min="0"
              step="0.01"
              value={value.bpmMax}
              onChange={(e) => update({ bpmMax: e.target.value })}
            />
          </label>
        </fieldset>
        <fieldset className="filter-range">
          <legend>Year range</legend>
          <label>
            From year
            <input
              type="number"
              min="1000"
              max="2999"
              step="1"
              value={value.yearMin}
              onChange={(e) => update({ yearMin: e.target.value })}
            />
          </label>
          <label>
            To year
            <input
              type="number"
              min="1000"
              max="2999"
              step="1"
              value={value.yearMax}
              onChange={(e) => update({ yearMax: e.target.value })}
            />
          </label>
        </fieldset>
      </div>
      {invalid && (
        <p role="alert">
          Minimum must not exceed maximum. Adjust the range to see results.
        </p>
      )}
      <p className="fine">
        Filters combine. Multiple genres, keys, formats or playlists match any
        selected value. Blank ranges include unknown values; missing values sort
        last.
      </p>
      {tracks.some(
        (t) => t.source !== "local" && t.source !== "demo" && !t.my_tags_loaded,
      ) && (
        <p className="fine">
          Some My Tags have not been imported.{" "}
          <button disabled={busy} onClick={onLoadTags}>
            Load My Tags from last scan
          </button>
        </p>
      )}
      {count > 0 && (
        <div className="filter-active">
          <strong>Active:</strong>
          {value.tags.map((id) => (
            <button
              key={id}
              onClick={() =>
                update({ tags: value.tags.filter((v) => v !== id) })
              }
            >
              {tags.get(id)?.name || "Tag from previous collection"} ×
            </button>
          ))}
          <button onClick={() => onChange({ ...emptyFilters })}>
            Clear music filters
          </button>
        </div>
      )}
    </details>
  );
}
