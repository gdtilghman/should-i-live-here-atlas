#!/usr/bin/env python3
"""Rank counties in SQL the way the browser ranks them in JavaScript.

This is the first step of the synthesis endgame, and the step where it is most
likely to go quietly wrong. The handoff records why: a ranked answer is a much
stronger claim than a map, and the difference between a join that DROPS a
county with a missing input and one that SCORES IT ZERO is the difference
between an honest answer and a confidently wrong one. SQL makes that mistake
easy, because a missing row is simply absent from a join.

So the rule is written here explicitly and proved by a test rather than
assumed. A county is ranked only when every selected input is available for it.
The HAVING clause below is that rule.

The score runs 0 to 100 and HIGHER MEANS MORE ADVERSE, because that is what
dist/composite.js produces. The best counties are therefore the lowest scores.
Nothing in the data knows this; it is a convention, and printing a "best"
list the wrong way round would be the easiest serious error to make here.

This reads the rehearsal database built by scripts/build-database.py. It does
not contact a network, and it is not a ranking feature: there is no framing, no
explanation of excluded counties, and no interface. It exists to prove the
arithmetic agrees with the browser before any of that is built.

Standard library only.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# The app's own starting weights, from initializeDefaultRecipe in dist/app.js.
DEFAULT_RECIPE = [
    ("disasters:hazard-fire", 40),
    ("cancer:066", 30),
    ("disasters:hazard-flood", 20),
    ("cancer:047-male", 10),
]

# A second recipe, ranked on every default run, because the default contains no
# hurricane input and so cannot show the not-applicable rule working. Inland
# counties have no hurricane exposure; the hurricane dataset declares that a
# best case, so they must be ranked, not dropped. scripts/test-ranking.cjs
# compares this output with the browser as well.
HURRICANE_RECIPE = [
    ("hazards:nri-hurricane", 50),
    ("hazards:nri-inland-flooding", 30),
    ("hazards:nri-tornado", 20),
]


def repo_root():
    return Path(__file__).resolve().parent.parent


def rank(db, recipe):
    """Return every county the recipe can score, worst first.

    Weights are normalized to sum to one, exactly as combine() does in
    dist/composite.js, so the score stays on the 0-100 scale whatever weights
    are given.
    """
    total = sum(weight for _, weight in recipe)
    if total <= 0:
        raise SystemExit("the recipe has no positive weight")

    placeholders = ",".join("(?, ?)" for _ in recipe)
    parameters = []
    for key, weight in recipe:
        parameters.extend([key, weight / total])

    # COUNT(*) = len(recipe) proves every selected input produced a row for
    # this county. The scaled IS NULL check proves each of those rows carried a
    # reading. Together they are the exclusion rule. Dropping either one would
    # let a county rank on partial data.
    sql = f"""
        WITH weight(dataset_key, share) AS (VALUES {placeholders})
        SELECT v.fips,
               c.name,
               c.state_name,
               SUM(v.scaled * weight.share) AS score
        FROM value v
        JOIN weight ON weight.dataset_key = v.dataset_key
        JOIN county c ON c.fips = v.fips
        GROUP BY v.fips
        HAVING COUNT(*) = ?
           AND SUM(CASE WHEN v.scaled IS NULL THEN 1 ELSE 0 END) = 0
        ORDER BY score DESC, v.fips
    """
    parameters.append(len(recipe))
    return [dict(zip(("fips", "name", "stateName", "score"), row))
            for row in db.execute(sql, parameters)]


def excluded_reasons(db, recipe):
    """Count why each county that cannot be ranked was left out.

    A ranking that cannot say who it left out, and why, is not usable. This is
    the evidence that the exclusions are data gaps rather than a broken join.
    """
    keys = [key for key, _ in recipe]
    placeholders = ",".join("?" for _ in keys)
    sql = f"""
        SELECT v.status, COUNT(*)
        FROM value v
        WHERE v.dataset_key IN ({placeholders}) AND v.scaled IS NULL
        GROUP BY v.status
        ORDER BY v.status
    """
    return dict(db.execute(sql, keys))


def parse_recipe(text):
    if not text:
        return DEFAULT_RECIPE
    recipe = []
    for part in text.split(","):
        key, _, weight = part.partition("=")
        recipe.append((key.strip(), float(weight)))
    return recipe


def main():
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(root / "work" / "atlas.sqlite"))
    parser.add_argument("--recipe", default="",
                        help="key=weight pairs, comma separated; default is the app's")
    parser.add_argument("--out", default=str(root / "work" / "ranking.json"))
    parser.add_argument("--hurricane-out", default=str(root / "work" / "ranking-hurricane.json"),
                        help="where the hurricane check recipe is written on a default run")
    parser.add_argument("--best", type=int, default=5)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"no database at {db_path}; run scripts/build-database.py")

    recipe = parse_recipe(args.recipe)
    runs = [(recipe, Path(args.out))]
    if not args.recipe:
        runs.append((HURRICANE_RECIPE, Path(args.hurricane_out)))

    db = sqlite3.connect(db_path)
    try:
        total_counties = db.execute("SELECT COUNT(*) FROM county").fetchone()[0]
        results = [(r, out, rank(db, r)) for r, out in runs]
        reasons = excluded_reasons(db, recipe)
    finally:
        db.close()

    for r, out, rows in results:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "recipe": [{"key": key, "weight": weight} for key, weight in r],
            "counties": total_counties,
            "ranked": rows,
        }, separators=(",", ":")), encoding="utf-8")
    ranked = results[0][2]

    print(f"inputs                {len(recipe)}")
    for key, weight in recipe:
        print(f"  {key:<28} {weight}")
    print(f"counties              {total_counties}")
    print(f"ranked                {len(ranked)}")
    print(f"excluded              {total_counties - len(ranked)}")
    print(f"missing readings      {reasons}")
    print()
    # Lowest score first, because a high score is the adverse end of the scale.
    print(f"least adverse {args.best} under these weights")
    for row in sorted(ranked, key=lambda r: r["score"])[:args.best]:
        print(f"  {row['score']:6.2f}  {row['name']}, {row['stateName']}")
    print()
    for r, out, rows in results:
        print(f"output                {out}  ({len(rows)} ranked)")
    if not ranked:
        sys.exit(1)


if __name__ == "__main__":
    main()
