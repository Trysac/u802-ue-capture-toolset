# Stack

## Used

| Tool | Why |
|---|---|
| Python >= 3.10 | Supported runtime for the library. |
| uv | Environment and build management. |
| hatchling | Build backend. |
| ruff | Lint and format. |
| mypy (strict) | Type checking; the package ships `py.typed`. |
| pytest + pytest-cov | Test runner with branch coverage. |
| hypothesis (dev) | Property tests, version >=6.100,<7. |
| gitleaks | Secret scanning. |
| GitHub Actions + Dependabot | CI and dependency updates. |

## Discarded

| Tool | Why not |
|---|---|
| Poetry | uv covers the same needs. |
| black + isort + flake8 | Replaced by ruff. |
| tox / nox | A single `scripts/check.py` is used locally. |
| Shell scripts for gates | Not portable to Windows. |
