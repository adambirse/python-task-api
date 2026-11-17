# Task API

A small, production-style REST API in Python, built to learn (and explain in an
interview) the things that matter in a real backend service:

- **Layered architecture**: thin controllers, a service layer for business rules, repositories for storage
- **Authentication**: bcrypt password hashing and JWT bearer tokens
- **Authorisation**: role-based (admin only) and ownership-based (only your own tasks)
- **Persistence**: SQLAlchemy 2.0 with PostgreSQL, and Alembic migrations
- **Testing**: unit tests with fakes and mocks, repository contract tests, and full HTTP API tests

It's deliberately small (one resource, tasks) so that every file is readable in a few minutes,
but it's structured the way a larger service would be.

**Stack:** FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · PostgreSQL · PyJWT · bcrypt · pytest · Ruff · mypy

---

## Quick start

### Option A: Docker (PostgreSQL included)

```bash
docker compose up --build
```

Open <http://localhost:8000/docs>. Migrations run automatically on start-up.

### Option B: Local Python

Needs Python 3.12+. Uses SQLite by default, so no database setup is required.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env               # then edit; delete DATABASE_URL to use SQLite
alembic upgrade head               # create the tables
uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs>, click **Authorize**, and log in.

A demo admin is created on start-up when `SEED_ADMIN_USERNAME` and `SEED_ADMIN_PASSWORD`
are set (they are in `.env.example` and `docker-compose.yml`): **admin / admin-password-123**.
This is for local demos only.

### Run the checks

```bash
pytest                    # all tests
pytest tests/unit         # just the fast unit tests
pytest --cov=app          # with coverage
ruff check . && mypy app  # lint and type check
```

---

## Project layout

```
app/
├── main.py                  # App factory, error-to-HTTP mapping, start-up/shutdown
├── api/
│   ├── deps.py              # Dependency injection wiring, get_current_user, require_role
│   └── routes/              # Controllers: auth.py, tasks.py, admin.py, health.py
├── services/                # Business logic: auth_service.py, task_service.py
├── repositories/
│   ├── interfaces.py        # What a repository must do (Protocols)
│   ├── sqlalchemy.py        # The real implementation (PostgreSQL / SQLite)
│   └── memory.py            # An in-memory fake, used by unit tests
├── domain/models.py         # Plain dataclasses: User, Task, Role, TaskStatus
├── schemas/                 # Pydantic request/response models (the API contract)
├── db/                      # SQLAlchemy engine, session, ORM table models
└── core/                    # Settings, security (hashing + JWT), domain exceptions
migrations/                  # Alembic migrations
tests/
├── unit/                    # Services and security, no HTTP, no database
├── integration/             # Repository contract tests (fake vs real database)
└── api/                     # Full stack over HTTP
```

---

## How a request flows

```
HTTP request
   │
   ▼
Route (controller)    app/api/routes/tasks.py     validate input, call ONE service method, shape output
   │  Depends(...)
   ▼
Service               app/services/task_service.py  business rules + ownership checks; raises domain errors
   │  via interface
   ▼
Repository            app/repositories/sqlalchemy.py  SQL in, domain objects out; never commits
   │
   ▼
Database session      app/db/session.py            one per request; commit on success, rollback on error
```

Each layer only knows about the one below it, and only through an interface:

| Layer | Knows about | Does **not** know about |
| --- | --- | --- |
| Route | HTTP, Pydantic schemas, the service | SQL, business rules |
| Service | Domain models, repository *interfaces*, domain errors | HTTP, FastAPI, SQLAlchemy |
| Repository | SQLAlchemy, ORM rows, domain models | HTTP, business rules |

### Why services raise `ForbiddenError` and not `HTTPException`

Services raise plain Python exceptions from `app/core/exceptions.py`. A single handler in
`app/main.py` maps them to status codes:

| Exception | Status | Meaning |
| --- | --- | --- |
| `AuthenticationError` | 401 | We don't know who you are |
| `ForbiddenError` | 403 | We know who you are, but you can't do this |
| `NotFoundError` | 404 | It doesn't exist |
| `ConflictError` | 409 | It clashes with the current state |
| *(Pydantic validation)* | 422 | The request body or query is malformed |

So the service could be reused from a CLI or a background job, the routes need no
`try/except`, and error responses are consistent everywhere.

### Dependency injection

FastAPI's `Depends` builds the object graph for each request in `app/api/deps.py`:

```python
def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(SqlAlchemyTaskRepository(session))
```

The service receives a repository; it never creates one. That one decision is what makes
the service unit-testable with an in-memory fake, and what would let you swap PostgreSQL for
something else without touching a single business rule.

---

## Authentication

`app/core/security.py` and `app/services/auth_service.py`

1. `POST /auth/register` stores the user with a **bcrypt hash**, never the password. Each hash
   has its own random salt and a deliberately slow work factor.
2. `POST /auth/token` (the standard OAuth2 password form) checks the password and returns a
   signed **JWT** containing the user id (`sub`), role and expiry (`exp`).
3. Protected routes depend on `get_current_user`, which reads the `Authorization: Bearer …`
   header, verifies the signature and expiry, then **reloads the user from the database**.

Details worth being able to explain:

- Login gives the same error for "unknown user" and "wrong password", so it can't be used to
  discover which usernames exist.
- The allowed algorithm is pinned when decoding, so a token can't pick `alg: none`
  (there's a test for this).
- The role is read from the database, not trusted from the token, so a deleted user's token
  stops working immediately.

## Authorisation

There are two kinds, and they deliberately live in different places.

**Role-based**, in the route layer. Only needs to know who you are:

```python
router = APIRouter(prefix="/admin", dependencies=[Depends(require_role(Role.ADMIN))])
```

Declared once on the router, so a new admin endpoint can't forget it. `TaskService.list_all_tasks`
also checks, as defence in depth.

**Ownership-based**, in the service layer. Needs the task loaded first, which only the
service has:

```python
def _ensure_can_access(actor: User, task: Task) -> None:
    if actor.is_admin or task.owner_id == actor.id:
        return
    raise ForbiddenError("You don't have access to this task")
```

Returning 403 here is a choice. Some APIs return 404 instead, so that other people's task ids
don't even reveal that the task exists. Both are defensible; know why you'd pick each.

---

## Persistence with SQLAlchemy

- **ORM models are separate from domain models.** `app/db/orm.py` describes tables;
  `app/domain/models.py` holds plain dataclasses. The repository maps between them, so no
  SQLAlchemy object (or lazy-loading surprise) ever leaks into a service.
- **SQLAlchemy 2.0 style**: typed `Mapped[...]` columns and `select()` statements. Queries
  use bound parameters, never string formatting, so they're safe from SQL injection.
- **One session per request = one transaction.** `session_scope` commits if the request
  succeeds and rolls back if anything raises. Repositories only `flush()` (to get generated
  ids); they never commit. A service that touches two repositories still gets one atomic
  transaction. This is the *unit of work* pattern.
- **Timezones**: `UTCDateTime` stores and returns timezone-aware UTC datetimes. PostgreSQL
  keeps timezones and SQLite drops them; this keeps both behaving the same.
- **Migrations with Alembic.** The app never creates or alters tables itself.

```bash
alembic upgrade head                                    # apply migrations
alembic revision --autogenerate -m "add due_date"       # after changing app/db/orm.py
alembic check                                           # fails if models and migrations differ (CI runs this)
```

The API is synchronous (plain `def` routes). FastAPI runs these in a thread pool, which is
simple and plenty fast for most services. Async SQLAlchemy is an option when you need very
high concurrency, at the cost of more complexity.

---

## Testing

60 tests, about one second. Three levels, each answering a different question:

### Unit tests: `tests/unit/`
*Are the business rules right?* Services are called directly with an in-memory repository.
No HTTP, no database.

`test_auth_service.py` shows two kinds of test double side by side:

- **Fakes** (`InMemoryUserRepository`): a real, working implementation. You assert on the
  resulting **state**: "after registering, the user can be found." Prefer these.
- **Mocks** (`unittest.mock.create_autospec`): record calls. You assert on the
  **interaction**: "`add()` was never called." Use when the interaction is the point.
  `create_autospec` makes the mock match the real interface, so typos fail loudly.

### Contract tests: `tests/integration/`
*Does the fake behave like the real thing?* The same tests run against the in-memory and the
SQLAlchemy repositories. If both pass, the unit tests can be trusted. They run on SQLite by
default and on PostgreSQL too when `TEST_DATABASE_URL` is set (CI does this).

### API tests: `tests/api/`
*Does it all work together over HTTP?* Real requests through the whole stack, checking status
codes, JSON and authorisation. Each test gets a fresh app on its own in-memory database
(see `tests/conftest.py`). `test_dependency_override_example` shows `app.dependency_overrides`,
which swaps any dependency for a test.

Useful pytest features on show: fixtures (`conftest.py`), `parametrize`, `pytest.raises`,
`monkeypatch` (bcrypt is turned down to its minimum cost so tests stay fast).

---

## API

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/health` | none | Liveness check, also pings the database |
| POST | `/auth/register` | none | Create an account |
| POST | `/auth/token` | none | Log in (form: `username`, `password`), returns a JWT |
| GET | `/auth/me` | user | Current user |
| GET | `/tasks?status=&limit=&offset=` | user | List **your** tasks |
| POST | `/tasks` | user | Create a task |
| GET | `/tasks/{id}` | owner or admin | Get a task |
| PATCH | `/tasks/{id}` | owner or admin | Partial update. Completed tasks are locked until reopened |
| DELETE | `/tasks/{id}` | owner or admin | Delete a task |
| GET | `/admin/tasks` | admin | List **everyone's** tasks |

Interactive docs are generated automatically at `/docs` (Swagger) and `/redoc`.

---

## Interview talking points

- **Why layers?** Each has one reason to change. Business rules are testable without HTTP or
  a database, and storage can change without touching them.
- **Where does validation go?** Shape and format (lengths, types, enums) in Pydantic schemas at
  the edge. Rules that depend on state ("completed tasks are locked") in the service.
- **401 vs 403?** 401: not authenticated. 403: authenticated but not allowed.
- **Why JWT?** Stateless: any instance can verify a token without a shared session store.
  The trade-off is revocation, which is why tokens are short-lived (30 minutes here).
- **Why bcrypt?** It's slow on purpose and salted, which makes stolen hashes expensive to crack.
- **Where's the transaction boundary?** The request. Repositories flush, the session scope commits.
- **Fakes or mocks?** Fakes for state, mocks for interactions. Too many mocks couple tests to
  implementation details.
- **How do you configure it?** Environment variables, validated at start-up by
  pydantic-settings, so a bad config fails fast.

## What I'd add for real production

- Refresh tokens and token revocation (a deny-list, or short tokens plus refresh)
- Rate limiting on `/auth/token` to slow down password guessing
- Structured JSON logging with a request id, plus metrics and tracing (OpenTelemetry)
- A secrets manager for `JWT_SECRET_KEY` instead of an environment file
- CORS settings if a browser front end calls it
- Cursor-based pagination for large lists
- Async SQLAlchemy if load required it

## License

MIT
