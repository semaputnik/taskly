# Taskly

[![Test Backend](../../actions/workflows/test-backend.yml/badge.svg)](../../actions/workflows/test-backend.yml)
[![Test Docker Compose](../../actions/workflows/test-docker-compose.yml/badge.svg)](../../actions/workflows/test-docker-compose.yml)

Веб-сервис на FastAPI. Основан на [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) (0.12.0+).

**Стек:** FastAPI + SQLModel + PostgreSQL на бэкенде, React 19 + TanStack Router/Query + Tailwind на фронтенде. Собранный фронтенд раздаёт сам FastAPI, отдельного фронтенд-контейнера нет. JWT-аутентификация, письма через React Email, локально их ловит Mailpit.

## Требования

| Инструмент | Версия |
|---|---|
| Python | 3.14+ (обязательно: код использует синтаксис 3.14) |
| [uv](https://docs.astral.sh/uv/) | свежий |
| [bun](https://bun.sh) | 1.3+ |
| Docker | любой актуальный |

## Первый запуск

```bash
cp .env.example .env        # затем заменить все changethis на реальные значения
docker compose up -d db mailpit
cd backend
uv sync
uv run bash scripts/prestart.sh   # миграции + создание суперпользователя
uv run fastapi dev                # http://localhost:8000
```

В другом терминале, из корня:

```bash
bun install
bun run dev                       # http://localhost:5173, с hot reload
```

Логин и пароль суперпользователя — `FIRST_SUPERUSER` и `FIRST_SUPERUSER_PASSWORD` в `.env`.

## Адреса

| Что | URL |
|---|---|
| Приложение и API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| Vite dev server | <http://localhost:5173> |
| Mailpit | <http://localhost:8025> |
| Adminer (только в полном compose-стеке) | <http://localhost:8080> |

## Команды на каждый день

```bash
# из backend/
uv run bash scripts/test.sh                                  # тесты + покрытие (в отдельной БД app_test)
uv run bash scripts/lint.sh                                  # mypy, ty, ruff
uv run alembic revision --autogenerate -m "описание"         # новая миграция
uv run alembic upgrade head                                  # применить миграции

# из корня
bash scripts/generate-client.sh     # перегенерировать TS-клиент после изменений API
uv run prek run --all-files         # все pre-commit проверки
bun run lint                        # biome для фронтенда
```

Тесты бэкенда используют отдельную базу `app_test` и не трогают данные разработки. Playwright-тесты (`bunx playwright test`) такой изоляции не имеют и пишут в основную базу.

## Конфигурация и секреты

- `.env` — локальные настройки и сгенерированные секреты, **в git не хранится**.
- `.env.example` — шаблон с плейсхолдерами; CI копирует его как `.env`, поэтому реальных секретов в нём быть не должно. Новые переменные добавляйте в оба файла.
- `frontend/.env` — только URL бэкенда и Mailpit для Vite, хранится в git.

## Документация

- [development.md](./development.md) — локальная разработка, Docker Compose, pre-commit
- [backend/README.md](./backend/README.md) — бэкенд, тесты, миграции, шаблоны писем
- [frontend/README.md](./frontend/README.md) — фронтенд, генерация клиента, Playwright
- [deployment.md](./deployment.md) — деплой в FastAPI Cloud (workflow пока запускается только вручную)
- [deployment-docker-compose.md](./deployment-docker-compose.md) — деплой на свой сервер

## Обновления из шаблона

Remote `upstream` указывает на шаблон и доступен только для чтения:

```bash
git fetch upstream
git merge upstream/master
```

## Лицензия

MIT, унаследована от шаблона — см. [LICENSE](./LICENSE).
