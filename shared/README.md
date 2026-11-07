# Shared contracts

The authoritative API contract is the backend OpenAPI document at `/api/v1/openapi.json` (generated
from Pydantic models). `shared/examples/` contains illustrative request/response payloads for
documentation and client tests. They are examples, not data returned by a live repository.

- Frontend types: `frontend/src/types/api.ts` mirror Pydantic responses.
- MCP tools shape a subset of the same responses.
- Do not add a second source of truth for schemas here; update the Pydantic model and regenerate.
