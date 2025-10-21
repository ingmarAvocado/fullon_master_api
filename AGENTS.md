# Fullon Master API - Agent Guidelines

## Build/Lint/Test Commands
- **Install**: `poetry install`
- **Run tests**: `make test` or `poetry run pytest tests/`
- **Run single test**: `poetry run pytest tests/unit/test_file.py::test_function`
- **Test with coverage**: `make test-cov`
- **Lint**: `make lint` (ruff + mypy)
- **Format**: `make format` (black + ruff)
- **Run server**: `make run` or `poetry run uvicorn fullon_master_api.main:app --reload`

## Code Style Guidelines
- **Python version**: 3.13+
- **Line length**: 100 characters
- **Imports**: stdlib → third-party → local (alphabetical within groups)
- **Types**: Use type hints everywhere, mypy strict
- **Naming**: snake_case (functions/vars), PascalCase (classes), UPPER_CASE (constants)
- **Docstrings**: Google-style triple quotes for modules/classes/functions
- **Error handling**: HTTPException(401/403/404/500) for API errors
- **Logging**: `from fullon_log import get_component_logger; logger = get_component_logger("component")`
- **Architecture**: Reference ADRs in comments for design decisions
- **Comments**: Minimal, explain why not what (except for complex business logic)