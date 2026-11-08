# Testing

## Running

```sh
uv run pytest --cov=ue_capture_toolset   # tests with coverage report
uv run python scripts/check.py           # every gate, as CI runs it
```

## Policy

- Branch coverage of `src/ue_capture_toolset` must stay at or above 85 %.
- Tests exercise the public API and assert return values and raised `CaptureError` codes.
- Tests use no network and no wall clock; time is passed as `at=` or `clock=`.
- Nothing in the test suite runs inside Unreal Engine.

## Tests that exist

The test files are listed under `tests/` (for example `tests/test_<module>.py` per core module), with shared fixtures in `tests/conftest.py`, the fake unreal module in `tests/fakes/unreal.py`, and golden Markdown in `tests/golden/`. Their coverage matches the acceptance criteria: resolution parsing, capture path uniqueness and sorting, git reading from loose refs, packed-refs, detached HEAD and missing `.git`, log tail selection, bug and contact sheet goldens, and pair transforms on the fake.

## Layout

`tests/test_<module>.py` mirrors each public module. Shared fixtures go in `tests/conftest.py`.
