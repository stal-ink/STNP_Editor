# Golden Outputs

Golden outputs are separated by generation target:

- `C/` — expected C generator output.
- `python/` — expected Python generator output.

Each golden tree is generated from its own input fixture under `fixtures/` and
is never derived from `examples/`:

- `C/regression_c/` — from `fixtures/C/regression_c.stnp` + `fixtures/C/stnp.build.json`.
- `python/regression_py/` — from `fixtures/python/regression_py.stnp` + `fixtures/python/stnp.build.json`.

`C/regression_c/vectors.json` is hand-written frame-level test data for the
regression fixture; it is not a generator artifact.

A target must have its own golden fixture before generator changes are considered regression-covered.
