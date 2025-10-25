# Contributing to ReelTrust

Thank you for your interest in contributing to ReelTrust! This guide will help you get started with development.

## Prerequisites

### System Requirements

ReelTrust requires the following system dependencies to be installed:

- [**uv**](https://docs.astral.sh/uv/) - For Python project management. This must be [installed](https://docs.astral.sh/uv/getting-started/installation/) before you start, via `brew install uv` or similar.
- [**ffmpeg**](https://ffmpeg.org/) - For video processing and compression
- [**chromaprint**](https://acoustid.org/chromaprint) (fpcalc) - For audio fingerprinting

### Installation

To automatically install system dependencies:

```bash
uv run poe install-system-deps
```

## Verify Installation**

```bash
# Run the CLI to verify everything works
uv run reeltrust --version

# Run tests
uv run poe test
```

## Development Workflow

### Running the CLI

```bash
# Sign a video file
uv run reeltrust sign path/to/video.mp4 -u "your_username"

# Get help
uv run reeltrust --help
uv run reeltrust sign --help
```

### Testing

```bash
# Run all tests
uv run poe test

# Run tests with coverage
uv run poe test-cov

# Run tests quickly (stop on first failure)
uv run poe test-fast
```

### Code Quality

```bash
# Format code
uv run poe format

# Check formatting
uv run poe format-check

# Lint code
uv run poe lint

# Fix auto-fixable lint issues
uv run poe fix

# Check dependencies
uv run poe deps

# Run all checks (format, lint, deps, test)
uv run poe check
```

### Available Poe Tasks

View all available tasks:

```bash
uv run poe --help
```

Common tasks:

- `poe install` - Install Python dependencies
- `poe install-system-deps` - Install system dependencies (macOS only)
- `poe test` - Run tests
- `poe lint` - Run linter
- `poe format` - Format code
- `poe check` - Run all checks
- `poe fix` - Auto-fix issues
- `poe clean` - Clean build artifacts

## Code Style

- We use **Ruff** for linting and formatting
- Follow **PEP 8** style guidelines
- Use **type hints** for all function signatures
- Write **docstrings** for all public functions and classes
- Keep functions focused and under 50 lines when possible

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Tests should be fast and independent
- Use descriptive test names

## Making Changes

1. **Create a new branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

   - Write code
   - Add/update tests
   - Update documentation

3. **Run checks**

   ```bash
   uv run poe check
   ```

4. **Commit your changes**

   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test changes
   - `refactor:` - Code refactoring
   - `chore:` - Maintenance tasks

5. **Push and create a Pull Request**

   ```bash
   git push origin feature/your-feature-name
   ```

## Getting Help

- **Issues**: Check existing [GitHub Issues](https://github.com/aaronsteers/ReelTrust/issues)
- **Discussions**: Start a [GitHub Discussion](https://github.com/aaronsteers/ReelTrust/discussions)
- **Specification**: Read [SPEC.md](SPEC.md) for project goals
- **Roadmap**: Check [project_plan.md](project_plan.md) for planned features

## Technical Debt & Future Work

See [project_plan.md](project_plan.md) for:

- Known technical debt
- Future enhancement plans
- Implementation priorities
- Architecture notes

## License

By contributing to ReelTrust, you agree that your contributions will be licensed under the MIT License.
