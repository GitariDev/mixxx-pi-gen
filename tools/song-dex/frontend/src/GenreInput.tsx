import { useEffect, useId, useMemo, useState } from "react";

export type GenreCount = { name: string; count: number };
type Option = { name: string; count: number; score: number; order: number };

let catalog: Promise<string[]> | undefined;
/** Every Noise at Once genre names, most popular first; fetched once per session. */
const everyNoise = () =>
  (catalog ??= fetch("/api/genres")
    .then((r) => r.json())
    .then((d) => d.genres as string[])
    .catch(() => []));

const fold = (s: string) =>
  s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
const pairs = (s: string) => {
  const found = new Set<string>();
  for (let i = 0; i < s.length - 1; i++) found.add(s.slice(i, i + 2));
  return found;
};
/** Lower is closer: exact, starts with, a word starts with, contains, then similar spelling. */
function closeness(query: string, name: string) {
  if (name === query) return 0;
  if (name.startsWith(query)) return 1;
  if ((" " + name).includes(" " + query)) return 2;
  if (name.includes(query)) return 3;
  const a = pairs(query),
    b = pairs(name);
  if (!a.size || !b.size) return null;
  let shared = 0;
  for (const pair of a) if (b.has(pair)) shared++;
  const similarity = (2 * shared) / (a.size + b.size);
  return similarity >= 0.55 ? 5 - similarity : null;
}

export function GenreInput({
  value,
  onChange,
  library,
}: {
  value: string;
  onChange: (value: string) => void;
  library: GenreCount[];
}) {
  const id = useId();
  const [names, setNames] = useState<string[]>([]),
    [open, setOpen] = useState(false),
    [active, setActive] = useState(-1);
  useEffect(() => {
    let live = true;
    everyNoise().then((list) => live && setNames(list));
    return () => {
      live = false;
    };
  }, []);
  const all = useMemo(() => {
    // The collection's own spellings come first and replace the catalog's.
    const seen = new Set(library.map((g) => fold(g.name)));
    return [
      ...library.map((g, i) => ({ ...g, key: fold(g.name), order: i })),
      ...names
        .filter((n) => !seen.has(fold(n)))
        .map((n, i) => ({
          name: n,
          count: 0,
          key: fold(n),
          order: library.length + i,
        })),
    ];
  }, [library, names]);
  const options = useMemo(() => {
    const query = fold(value);
    if (!query) return all.slice(0, 8).map((g) => ({ ...g, score: 0 }));
    const found: Option[] = [];
    for (const g of all) {
      const score = closeness(query, g.key);
      if (score !== null) found.push({ ...g, score });
    }
    return found
      .sort((a, b) => a.score - b.score || a.order - b.order)
      .slice(0, 8);
  }, [all, value]);
  const choose = (name: string) => {
    onChange(name);
    setOpen(false);
    setActive(-1);
  };
  const shown = open && options.length > 0;
  return (
    <div className="genre-picker">
      <input
        role="combobox"
        aria-expanded={shown}
        aria-controls={id}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${id}-${active}` : undefined}
        autoComplete="off"
        maxLength={255}
        placeholder="Type to search genres"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            const step = e.key === "ArrowDown" ? 1 : -1;
            if (options.length)
              setActive(
                active < 0
                  ? step > 0
                    ? 0
                    : options.length - 1
                  : (active + step + options.length) % options.length,
              );
          } else if (e.key === "Enter" && shown && active >= 0) {
            e.preventDefault();
            choose(options[active].name);
          } else if (e.key === "Escape" && shown) {
            e.stopPropagation();
            setOpen(false);
          }
        }}
      />
      {shown && (
        <ul className="genre-options" role="listbox" id={id}>
          {options.map((g, i) => (
            <li
              key={g.name}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : undefined}
              // Keep focus in the input so the choice lands before blur closes the list.
              onMouseDown={(e) => {
                e.preventDefault();
                choose(g.name);
              }}
            >
              <span>{g.name}</span>
              <small>
                {g.count ? `${g.count} in your library` : "Every Noise at Once"}
              </small>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
