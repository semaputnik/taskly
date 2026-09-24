# Taskly

[![Test Backend](../../actions/workflows/test-backend.yml/badge.svg)](../../actions/workflows/test-backend.yml)
[![Test Docker Compose](../../actions/workflows/test-docker-compose.yml/badge.svg)](../../actions/workflows/test-docker-compose.yml)

A FastAPI web service. Based on [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) (0.12.0+).

**Stack:** FastAPI + SQLModel + PostgreSQL on the backend, React 19 + TanStack Router/Query + Tailwind on the frontend. FastAPI serves the built frontend itself — there is no separate frontend container. JWT authentication, emails via React Email, caught locally by Mailpit.

## Requirements

| Tool | Version |
|---|---|
| Python | 3.14+ (required: the code uses 3.14 syntax) |
| [uv](https://docs.astral.sh/uv/) | latest |
| [bun](https://bun.sh) | 1.3+ |
| Docker | any recent version |

## First run

```bash
cp .env.example .env        # then replace every changethis with a real value
docker compose up -d db mailpit
cd backend
uv sync
uv run bash scripts/prestart.sh   # migrations + superuser creation
uv run fastapi dev                # http://localhost:8000
```

In another terminal, from the repository root:

```bash
bun install
bun run dev                       # http://localhost:5173, with hot reload
```

The superuser login and password are `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD` in `.env`.

## URLs

| What | URL |
|---|---|
| App and API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| Vite dev server | <http://localhost:5173> |
| Mailpit | <http://localhost:8025> |
| Adminer (only in the full compose stack) | <http://localhost:8080> |

## Everyday commands

```bash
# from backend/
uv run bash scripts/test.sh                                  # tests + coverage (in a separate app_test database)
uv run bash scripts/lint.sh                                  # mypy, ty, ruff
uv run alembic revision --autogenerate -m "description"      # new migration
uv run alembic upgrade head                                  # apply migrations

# from the repository root
bash scripts/generate-client.sh     # regenerate the TS client after API changes
uv run prek run --all-files         # all pre-commit checks
bun run lint                        # biome for the frontend
```

Backend tests use a separate `app_test` database and never touch development data. Playwright tests (`bunx playwright test`) have no such isolation and write to the main database.

## Configuration and secrets

- `.env` — local settings and generated secrets, **not stored in git**.
- `.env.example` — a template with placeholders; CI copies it as `.env`, so it must not contain real secrets. Add new variables to both files.
- `frontend/.env` — only the backend and Mailpit URLs for Vite, stored in git.

## Documentation

- [development.md](./development.md) — local development, Docker Compose, pre-commit
- [backend/README.md](./backend/README.md) — backend, tests, migrations, email templates
- [frontend/README.md](./frontend/README.md) — frontend, client generation, Playwright
- [deployment.md](./deployment.md) — deploying to FastAPI Cloud (the workflow is still triggered manually only)
- [deployment-docker-compose.md](./deployment-docker-compose.md) — deploying to your own server

## Updates from the template

The `upstream` remote points at the template and is read-only:

```bash
git fetch upstream
git merge upstream/master
```

## License

MIT, inherited from the template — see [LICENSE](./LICENSE).
