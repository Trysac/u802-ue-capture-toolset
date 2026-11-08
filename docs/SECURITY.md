# Security notes

## Threat model

The core performs no I/O except reading `.git` files in a given folder. The adapter writes files and calls the Unreal console. Relevant limits are listed below.

### Defended

- **Paths outside Saved**: `before` and `log_path` are resolved and rejected unless inside the Saved folder (`invalid_path`, `unknown_capture`).
- **Quote injection in console command**: `saved_dir` containing a double quote is rejected (`invalid_path`).
- **Oversized input**: log text above 8,000,000 characters, notes above 20,000 characters, and sidecars above the size limit are rejected.
- **Unbounded output**: contact sheets hold at most 200 captures; series hold at most 50 cameras; list results are capped at 500.
- **Malformed sidecars**: fields are type-checked; unreadable sidecars are counted as skipped in `list_captures`.
- **Markdown injection**: titles, labels and log lines are flattened, and backticks replaced.
- **Git ref traversal**: refs must match a safe pattern and not contain `..`.

### Not defended

- Files in the Saved folder are trusted; the library does not authenticate them.
- Log content is shown in reports as given after flattening; secrets in logs are not removed.
- The adapter is unverified inside Unreal; behaviour of the real `unreal` API is not tested.
- Symlinks inside the Saved folder are resolved, but no further hardening against races (TOCTOU) is applied.
- `read_git_commit` trusts the content of `.git` files it reads.

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
