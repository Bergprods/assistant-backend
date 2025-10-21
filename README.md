# Assistant Backend

## Run all tests

You can run all backend tests from VS Code tasks or via pytest.

- VS Code Task:
  - Run task: Run all backend tests
- CLI (PowerShell):

```powershell
pytest -q assistant-backend/tests
```

## Migrations (Alembic)

Alembic is configured. Ensure `DATABASE_URL` is set, then:

```powershell
alembic upgrade head
```

## Endpoints added
- POST /api/orchestrator/log
- GET /api/orchestrator/log/{sessionId}?includeOriginal=false
- GET /api/orchestrator/router_messages/{sessionId}?limit=20&offset=0&since=
- GET /api/orchestrator/errors/{sessionId}?limit=50&offset=0&details=false
