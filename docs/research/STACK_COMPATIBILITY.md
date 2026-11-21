# Initial Stack Compatibility Review

Reviewed: 2026-11-21. This is a compatibility baseline, not a completed dependency lock or a Windows test result.

| Component | Selected range | Evidence / rationale |
|---|---|---|
| Python | >=3.12,<3.16 | The selected PySide6 distribution declares support from Python 3.10 up to, but excluding, 3.16. Targeting 3.12 keeps the initial runtime conservative. |
| PySide6 | >=6.8,<7 | Qt for Python is the native Qt binding and supports Windows x64 and Python 3.12. Exact wheel/build compatibility must be tested on the CI matrix. |
| SQLAlchemy | >=2.1,<2.2 | SQLAlchemy 2.1 is the current series in November 2026; it requires Python 3.11+ and includes 3.12 support. |
| Alembic | >=1.20,<1.21 | Current documentation supports Python 3.10+ and SQLAlchemy 2.0+, so it is compatible with SQLAlchemy 2.1. |
| Pydantic | >=2.14,<3 | Pydantic v2.14 declares support for Python 3.11+ and 3.12. |

## Sources

- PySide6 package metadata: https://pypi.org/project/PySide6/
- Qt for Python platform and compatibility overview: https://wiki.qt.io/PySide
- SQLAlchemy current release status: https://www.sqlalchemy.org/download.html
- SQLAlchemy 2.1 Python compatibility notes: https://docs.sqlalchemy.org/en/21/changelog/migration_21.html
- Alembic documentation: https://alembic.sqlalchemy.org/en/latest/front.html
- Pydantic package release metadata: https://pypi.org/project/pydantic/

## Lockfile decision

No `uv.lock` or `requirements.lock` is committed at this stage. The current execution environment has no mounted checkout/runtime, so a resolver-generated lock and Windows wheel installation cannot be verified here. CI currently resolves the declared ranges. Generate and commit the lockfile only after resolving and testing on the supported Windows Python environment; CI should then switch to locked/sync-only mode.
