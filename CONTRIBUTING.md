# Contributing to ATLAS Bot

Thank you for your interest in contributing to ATLAS Bot! This document provides guidelines and information for contributors.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ATLAS-bot.git
   cd atlas-bot
   ```
3. Set up the development environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   pre-commit install
   ```

## Development Workflow

### Making Changes

1. Create a new branch for your feature/fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and ensure they follow our coding standards

3. Run the linters:
   ```bash
   ruff check .
   ruff format .
   ```

4. Commit your changes with a descriptive message:
   ```bash
   git commit -m "feat: add new feature"
   ```

### Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### Pull Request Process

1. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a Pull Request against the `main` branch

3. Fill out the PR template with:
   - Description of changes
   - Related issues
   - Testing performed

4. Wait for review and address any feedback

## Code Style

- **Python**: We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- **Markdown/JSON/YAML**: We use [Prettier](https://prettier.io/) for formatting
- **Type hints**: Use type hints for function parameters and return values
- **Docstrings**: Use docstrings for modules, classes, and functions

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

- Python version
- Operating system
- Claude Code CLI version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

### Feature Requests

For feature requests, please describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

## Questions?

Feel free to open an issue for any questions about contributing.

Thank you for helping make ATLAS Bot better! 🤖
