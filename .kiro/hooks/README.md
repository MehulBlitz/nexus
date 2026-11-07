# Kiro hooks

No hook has been installed through the Kiro UI in this environment. This file records the intended
configuration so it can be added and verified in a real Kiro session.

Kiro hooks are configured through the supported interface; the exact schema depends on the Kiro
version. The following intents are deliberately non-destructive:

| Trigger | Intent | Command |
|---|---|---|
| Backend file saved | Lint changed backend code | `cd backend && ruff check .` |
| Backend file saved | Run focused tests | `cd backend && pytest -q` |
| Frontend file saved | Typecheck and lint | `cd frontend && npm run typecheck && npm run lint` |
| API schema changed | Regenerate/check OpenAPI documentation | `cd backend && python -c "from app.main import create_app; create_app().openapi()"` |
| Spec task completed | Update `BUILD_STATUS.md` manually | none (agent prompt) |
| Before commit | Full check | `make check` |

Rules:

- Hooks must not delete files, rewrite large sections, push, deploy, or run Docker.
- A hook that runs tests must preserve the exit status and surface failures.
- Do not add hooks that install dependencies automatically.
- Never place tokens in hook commands.

Status: **NOT INSTALLED**. Do not claim hook execution as evidence until configured and observed in
Kiro.
