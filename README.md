# ue-capture-toolset

[![PyPI version](https://img.shields.io/pypi/v/trysac-ue-capture-toolset)](https://pypi.org/project/trysac-ue-capture-toolset/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-ue-capture-toolset)](LICENSE)
[![CI](https://github.com/Trysac/u802-ue-capture-toolset/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u802-ue-capture-toolset/actions/workflows/ci.yml)

Pure core and unreal adapter of an Unreal MCP toolset for reproducible captures with JSON sidecars, bug evidence and Markdown contact sheets.

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-ue-capture-toolset
# or
uv add trysac-ue-capture-toolset
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import ue_capture_toolset

# normalize() trims surrounding whitespace and lower-cases the text.
print(ue_capture_toolset.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    ue_capture_toolset.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
