# Coding standards

- **Python:** 3.12+, full type hints, Ruff for lint and format, Pydantic for IO schemas. snake_case modules and functions, PascalCase classes.
- **TypeScript:** `strict: true`, no `any` without a comment, PascalCase components, camelCase everything else.
- **Structure:** one responsibility per module. No large mixed-purpose files.
- **Errors:** raise typed `AppError` subclasses in services; the API layer maps them to a consistent JSON error body. Never leak stack traces to clients.
- **Logging:** structured JSON, include correlation ID, never log secrets, tokens or source content.
- **Docs:** public functions get docstrings explaining behaviour, not restating names.
- **Tests:** every feature ships with tests in the same change.
