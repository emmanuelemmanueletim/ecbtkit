# Contributing to eCBTKit

Thank you for your interest in contributing!

## Development setup

```bash
git clone https://github.com/emmanuelemmanueletim/ecbtkit.git
cd ecbtkit
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

## Code style

- Black (line length 100)
- Ruff for linting
- Type hints encouraged

## Pull requests

1. Fork the repository
2. Create a feature branch
3. Add tests for new behaviour
4. Ensure the test suite passes
5. Open a PR with a clear description

## Scope

Please keep contributions focused on the CBT domain. Avoid turning eCBTKit into a general LMS or web framework.
