# Contributing to AuthSystem

Thanks for your interest in contributing. Here's everything you need to get started.

## Ways to Contribute

- Report bugs by opening a GitHub issue
- Suggest features or improvements via issues
- Submit pull requests for bug fixes or new features
- Improve documentation

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Steve2009729/auth-system.git
cd auth-system

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies (including dev extras)
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env

# Start backing services
docker-compose up -d db redis

# Run migrations
authsystem migrate

# Run the dev server
authsystem serve
```

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

All tests must pass before submitting a PR. New features should include tests.

## Code Style

- Follow PEP 8 for Python code
- Use type hints throughout
- Keep functions focused and small
- Write docstrings for public functions and classes

Lint your changes before submitting:

```bash
pip install ruff
ruff check app/ tests/
```

## Submitting a Pull Request

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and add tests
4. Run tests: `pytest tests/ -v`
5. Push and open a PR against `main`
6. Fill out the PR template describing what changed and why

## Bug Reports

When filing a bug, please include:

- Your Python version and OS
- Steps to reproduce the issue
- Expected vs actual behavior
- Relevant logs or error messages

## Security Vulnerabilities

Do **not** file public issues for security vulnerabilities. Instead, email the maintainer directly so it can be patched before disclosure.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
