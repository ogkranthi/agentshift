# Contributing to AgentShift

Thanks for your interest in contributing! AgentShift is an open-source CLI transpiler for converting AI agents between platforms.

## Quick Start

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/agentshift.git
cd agentshift

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in dev mode
pip install -e ".[dev]"

# Verify
agentshift --help
pytest tests/
```

## How to Contribute

### Adding a New Platform

This is the most impactful contribution. Each platform needs:

1. **Format spec** (`specs/{platform}-format.md`) — document the agent definition format with examples
2. **Parser** (`src/agentshift/parsers/{platform}.py`) — reads the platform's format into IR
3. **Emitter** (`src/agentshift/emitters/{platform}.py`) — writes IR to the platform's format
4. **Tests** (`tests/test_{platform}.py`) — unit + integration tests
5. **Test fixture** (`tests/fixtures/{platform}-example/`) — a real agent definition

Start by opening a [Platform Request issue](https://github.com/ogkranthi/agentshift/issues/new?template=platform_request.yml) to discuss the approach.

### Architecture

```
Source Agent → Parser → IR (Intermediate Representation) → Emitter → Target Config
```

- **Parsers** read a platform-specific format and produce an `AgentIR` object
- **Emitters** take an `AgentIR` object and write platform-specific files
- **IR** is the universal agent model — see `specs/ir-schema.json`

### Fixing Bugs / Adding Features

1. Check [open issues](https://github.com/ogkranthi/agentshift/issues) for something to work on
2. Comment on the issue to claim it
3. Fork, branch, implement, test, PR

## Development Guidelines

### Code Style

- **Python 3.11+** required
- Type hints on all function signatures
- Use `pathlib.Path` for file operations
- Use `rich` for CLI output
- Dataclasses or Pydantic models for structured data
- f-strings for formatting

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_parsers.py -v

# Run with coverage
pytest tests/ --cov=agentshift --cov-report=term-missing
```

- Every parser and emitter must have tests
- Use `tmp_path` fixture for file system operations
- Include both happy-path and error-handling tests
- Test fixtures go in `tests/fixtures/`

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Keep commits atomic — one logical change per commit
- Write clear commit messages explaining *why*, not just *what*

## Pull Request Process

1. **Branch from `main`** — use `feat/{description}`, `fix/{description}`, or `platform/{name}`
2. **One concern per PR** — don't mix features, fixes, and refactors
3. **Tests required** — PRs without tests for new functionality will not be merged
4. **CI must pass** — lint, tests, and type checks must all pass
5. **Review required** — all PRs require at least one approving review
6. **No secrets** — never commit API keys, tokens, or credentials
7. **Update specs** — if your change affects the IR or a platform format, update the relevant spec

### PR Size Guidelines

- **Small PRs preferred** — under 300 lines changed
- If your change is large, break it into smaller PRs
- Spec PRs and implementation PRs should be separate

## Project Structure

```
agentshift/
├── src/agentshift/       # Main package
│   ├── cli.py            # CLI entry point (Typer)
│   ├── ir.py             # IR model
│   ├── parsers/          # Platform parsers (format → IR)
│   └── emitters/         # Platform emitters (IR → format)
├── specs/                # Platform format specifications
├── tests/                # Test suite
│   └── fixtures/         # Test agent definitions
├── docs/                 # Documentation
└── examples/             # Example conversions
```

## Getting Help

- [Open a discussion](https://github.com/ogkranthi/agentshift/discussions) for questions
- [Open an issue](https://github.com/ogkranthi/agentshift/issues) for bugs or feature requests
- Check existing issues before opening a new one

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
