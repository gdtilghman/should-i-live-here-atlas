# Contributing

Thank you for your help. This page tells you how changes get into the atlas.

## How changes get merged

- The owner, @gdtilghman, reviews every pull request.
- Only the owner merges. A merge to `master` updates the live site.
- The owner can close a pull request that does not fit the project.
  The owner can also ask for changes first.
- For a large change, open an issue first. Agree on the plan before you
  write code.

## What fits

- Public federal data only. Check the reuse terms of each source first.
- County level only, for the 3,107 counties of the lower 48 states.
- Keep missing values apart from zero. A county without data shows
  "unavailable", never a low value.
- Add a source audit in `docs/` for each new layer.
- No accounts, ads, tracking or personal data.

## Before you open a pull request

1. Run the tests:

   ```bash
   node --test scripts/test-*.cjs
   ```

2. Run the Python test for each family you changed, for example
   `python scripts/test-water.py`.
3. Open the site with `python scripts/serve.py` and check your change.
4. Fill in the pull request checklist.

## License of contributions

You keep your copyright. By opening a pull request, you agree that your
code uses the [Apache License 2.0](LICENSE) and your prepared data uses
[CC BY 4.0](LICENSE-DATA.md).

## Security problems

Do not open a public issue. See [SECURITY.md](SECURITY.md).
