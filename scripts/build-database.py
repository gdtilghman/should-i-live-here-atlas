#!/usr/bin/env python3
"""Build a local SQLite rehearsal of the atlas database.

The atlas scores counties in the browser. The endgame is different: a person
states what matters to them and the system returns the few best counties. That
is a large input and a tiny output, so the arithmetic belongs beside the data
rather than in a page that must first download it.

Cloudflare D1 is SQLite. This script builds the same schema
locally so it can be proved before anything depends on a hosted database. It is
a rehearsal, not a deployment. It never contacts a network and never needs a
credential.

It also answers the only scale question that matters: whether the real thing
fits. Run it and read the projected size at 150 datasets.

Standard library only. No network. Input files are never modified.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

FAMILIES = ("cancer", "disasters", "community", "hazards", "healthcare", "employment", "broadband", "places", "air", "wildfire", "water", "traffic", "climate", "storms", "crime")

# The invariant this schema exists to protect. A missing, suppressed,
# policy-withheld or not-applicable reading must never be confused with a real
# measured zero. In the browser that is a convention. Here the database refuses
# to hold a row that breaks it, so a future loader cannot quietly coerce one.
SCHEMA = """
CREATE TABLE county (
  fips       TEXT PRIMARY KEY,
  state      TEXT NOT NULL,
  name       TEXT NOT NULL,
  state_name TEXT NOT NULL
);

CREATE TABLE dataset (
  key          TEXT PRIMARY KEY,   -- 'family:id', the key the app already uses
  family       TEXT NOT NULL,
  id           TEXT NOT NULL,
  title        TEXT NOT NULL,
  unit         TEXT,
  period       TEXT,
  direction    TEXT NOT NULL,
  -- NULL, or 'best-case' when the source's not-applicable means no exposure.
  not_applicable_means TEXT CHECK (not_applicable_means IS NULL
                                   OR not_applicable_means = 'best-case'),
  source_url   TEXT,
  note         TEXT,
  scale_min    REAL,
  scale_max    REAL,
  scale_fence  REAL,
  scale_count  INTEGER NOT NULL,
  has_extremes INTEGER NOT NULL,
  UNIQUE (family, id)
);

CREATE TABLE value (
  dataset_key TEXT NOT NULL REFERENCES dataset(key),
  fips        TEXT NOT NULL REFERENCES county(fips),
  status      TEXT NOT NULL,
  value       REAL,
  scaled      REAL,
  extreme     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (dataset_key, fips),
  CHECK ((status = 'available') = (value IS NOT NULL)),
  -- An available reading is always scored. Otherwise only a not-applicable
  -- reading may carry a score, and then only the best case, 0. Whether its
  -- dataset declared that is a question about another table, which no CHECK
  -- can ask, so the loader enforces it and verify() queries it back.
  CHECK (status != 'available' OR scaled IS NOT NULL),
  CHECK (scaled IS NULL OR status IN ('available', 'not-applicable')),
  CHECK (status != 'not-applicable' OR scaled IS NULL OR scaled = 0),
  CHECK (scaled IS NULL OR (scaled BETWEEN 0 AND 100))
);

CREATE INDEX value_by_fips ON value (fips);
"""
# WITHOUT ROWID would be smaller here. It is not used, because D1's support for
# it is not something this project has verified, and an unverified assumption is
# not worth the bytes.


def repo_root():
    return Path(__file__).resolve().parent.parent


def load_counties(db, path):
    geojson = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in geojson.get("features") or []:
        props = feature.get("properties") or {}
        rows.append((props.get("fips"), props.get("state"),
                     props.get("name"), props.get("stateName")))
    db.executemany(
        "INSERT INTO county (fips, state, name, state_name) VALUES (?, ?, ?, ?)", rows)
    return len(rows)


def load_values(db, data_dir, normalized_path):
    """Load the dataset and value tables, and report what was left out."""
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    known_fips = {row[0] for row in db.execute("SELECT fips FROM county")}

    datasets = []
    values = []
    source_records = 0
    skipped = {}

    for family in FAMILIES:
        source = json.loads((data_dir / f"{family}.json").read_text(encoding="utf-8"))
        built = (normalized.get("families") or {}).get(family) or {}
        source_datasets = source.get("datasets") or []
        built_datasets = built.get("datasets") or []
        if len(source_datasets) != len(built_datasets):
            raise SystemExit(f"{family}: {len(built_datasets)} normalized datasets "
                             f"against {len(source_datasets)} in the source")

        for dataset, scored in zip(source_datasets, built_datasets):
            if dataset.get("id") != scored.get("id"):
                raise SystemExit(f"{family}: dataset order differs, "
                                 f"{dataset.get('id')} against {scored.get('id')}")
            key = f"{family}:{dataset['id']}"
            stats = scored.get("stats") or {}
            datasets.append((
                key, family, dataset["id"], dataset.get("title"),
                dataset.get("unit"), dataset.get("period"),
                dataset.get("direction") or "higher-worse",
                dataset.get("notApplicableMeans"),
                dataset.get("sourceUrl") or source.get("sourceUrl"),
                dataset.get("note") or source.get("note"),
                stats.get("min"), stats.get("max"), stats.get("fence"),
                stats.get("count") or 0, 1 if stats.get("hasExtremes") else 0,
            ))

            scored_records = scored.get("records") or {}
            for fips, record in (dataset.get("records") or {}).items():
                source_records += 1
                # The atlas geometry is the contiguous states. Sources that
                # reach beyond it are not an error, but the number must be
                # stated rather than hidden.
                if fips not in known_fips:
                    skipped[family] = skipped.get(family, 0) + 1
                    continue
                scaled = scored_records.get(fips) or {}
                if (record.get("status") == "not-applicable"
                        and scaled.get("scaled") is not None
                        and dataset.get("notApplicableMeans") != "best-case"):
                    raise SystemExit(f"{key}/{fips}: not-applicable is scored, but the "
                                     "dataset does not declare it a best case")
                values.append((key, fips, record.get("status"), record.get("value"),
                               scaled.get("scaled"), 1 if scaled.get("extreme") else 0))

    db.executemany(
        """INSERT INTO dataset (key, family, id, title, unit, period, direction,
             not_applicable_means, source_url, note, scale_min, scale_max,
             scale_fence, scale_count, has_extremes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", datasets)
    db.executemany(
        """INSERT INTO value (dataset_key, fips, status, value, scaled, extreme)
           VALUES (?, ?, ?, ?, ?, ?)""", values)
    return source_records, skipped


def verify(db, db_path, source_records, skipped):
    counties = db.execute("SELECT COUNT(*) FROM county").fetchone()[0]
    datasets = db.execute("SELECT COUNT(*) FROM dataset").fetchone()[0]
    values = db.execute("SELECT COUNT(*) FROM value").fetchone()[0]
    statuses = dict(db.execute(
        "SELECT status, COUNT(*) FROM value GROUP BY status ORDER BY status"))
    nulls = db.execute("SELECT COUNT(*) FROM value WHERE value IS NULL").fetchone()[0]
    zeros = db.execute("SELECT COUNT(*) FROM value WHERE value = 0").fetchone()[0]
    distinct_fips = db.execute("SELECT COUNT(DISTINCT fips) FROM value").fetchone()[0]
    mismatched = db.execute(
        "SELECT COUNT(*) FROM value WHERE (status = 'available') != (value IS NOT NULL)"
    ).fetchone()[0]

    undeclared = db.execute(
        """SELECT COUNT(*) FROM value v JOIN dataset d ON d.key = v.dataset_key
           WHERE v.status = 'not-applicable' AND v.scaled IS NOT NULL
             AND d.not_applicable_means IS NOT 'best-case'""").fetchone()[0]
    assumed = dict(db.execute(
        """SELECT dataset_key, COUNT(*) FROM value
           WHERE status = 'not-applicable' AND scaled IS NOT NULL
           GROUP BY dataset_key ORDER BY dataset_key"""))

    megabytes = db_path.stat().st_size / (1024 * 1024)
    projected = megabytes * 150 / datasets if datasets else 0
    total_skipped = sum(skipped.values())

    print(f"counties              {counties}")
    print(f"datasets              {datasets}")
    print(f"values                {values}")
    print(f"distinct counties     {distinct_fips}")
    print(f"status distribution   {statuses}")
    # Two different things. A null is an absent reading; a zero is a reading of
    # zero. Merging them is the failure this project works hardest to avoid.
    print(f"null values           {nulls}")
    print(f"meaningful zeros      {zeros}")
    print(f"assumed best case     {assumed}")
    print()
    print(f"source records        {source_records}")
    print(f"skipped, unknown fips {total_skipped} {skipped if skipped else ''}")
    print(f"expected rows         {source_records - total_skipped}")
    print()
    print(f"database              {megabytes:.1f} MB")
    print(f"projected at 150      {projected:.0f} MB against D1's 10240 MB limit")
    print()

    ok = True
    if mismatched:
        # The CHECK should make this impossible. If it happens, the constraint
        # is not doing its job and nothing else here can be trusted.
        print(f"FAIL {mismatched} rows where status and value disagree")
        ok = False
    if undeclared:
        print(f"FAIL {undeclared} not-applicable rows scored in a dataset that "
              "does not declare a best case")
        ok = False
    if values != source_records - total_skipped:
        print(f"FAIL inserted {values}, expected {source_records - total_skipped}")
        ok = False
    if ok:
        print("every source record is stored or accounted for")
    return ok


def build(data_dir, db_path):
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(db_path)
    try:
        # Set before any statement opens a transaction. Inside one it is
        # silently ignored, and a foreign key that is never enforced is worse
        # than none, because it reads as a guarantee.
        db.execute("PRAGMA foreign_keys = ON")
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1, \
            "foreign keys did not turn on"
        db.executescript(SCHEMA)

        print(f"counties loaded       {load_counties(db, data_dir / 'counties.geojson')}")
        source_records, skipped = load_values(db, data_dir, data_dir / "normalized.json")
        db.commit()
        print()
        return verify(db, db_path, source_records, skipped)
    finally:
        db.close()


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(root / "dist" / "data"))
    parser.add_argument("--out", default=str(root / "work" / "atlas.sqlite"))
    args = parser.parse_args()
    out = Path(args.out)
    if not build(Path(args.data), out):
        sys.exit(1)
    print(f"output                {out}")


if __name__ == "__main__":
    main()
