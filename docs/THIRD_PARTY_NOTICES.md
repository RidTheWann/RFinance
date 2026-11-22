# Third-party license notices

RFinance is licensed under `GPL-3.0-only`. This file records the licenses of the packages actually installed when this document was prepared (2026-11-22, Python 3.14 environment), read from their distribution metadata rather than assumed. Versions in a future release may differ; regenerate this list from the locked environment before shipping a binary.

## Application dependency licenses

| Package | Version | License expression (from metadata) | Role |
|---|---|---|---|
| PySide6 | 6.12.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | Desktop UI bindings; selected under GPL-3.0-only for this application |
| shiboken6 | 6.12.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | PySide6 binding runtime |
| SQLAlchemy | 2.1.9 | `MIT` | Persistence / ORM |
| Alembic | 1.20.1 | `MIT` | Schema migrations |
| pydantic | 2.14.4 | `MIT` | Data-contract validation |

## Development and test dependency licenses

| Package | Version | License expression | Role |
|---|---|---|---|
| pytest | 9.2.0 | `MIT` | Test runner |
| pytest-qt | 4.5.0 | `MIT` | Qt test integration |
| hypothesis | 6.170.17 | `MPL-2.0` | Property-based testing |
| ruff | 0.17.6 | `MIT` | Lint / format |
| mypy | 1.20.2 | `MIT` | Static typing |
| bandit | 1.9.4 | `Apache-2.0` | Security scanning |
| pip-audit | 2.10.1 | (see installed metadata) | Dependency vulnerability audit |
| setuptools | 84.2.1 | `MIT` | Build backend |

## Qt for Python obligations

Qt for Python Community is distributed under LGPLv3/GPLv3. RFinance imports Qt Core, Gui, Widgets and Test only; it does not use GPL-only Qt modules such as Qt Charts, Qt Data Visualization, Qt WebEngine or Qt Virtual Keyboard. When distributing a frozen Windows build:

1. Keep intact all Qt and PySide6 copyright, license and third-party notices in the bundled runtime directory.
2. Include the GPLv3 text (`LICENSE`) and identify RFinance as GPL-3.0-only.
3. Provide the Corresponding Source for the RFinance application as required by GPLv3 §6, including build scripts and packaging configuration.
4. Preserve the third-party notices that Qt for Python documents at https://doc.qt.io/qtforpython-6/licenses.html and Qt's own third-party license list.
5. Do not switch to commercial Qt wheels unless the commercial license terms are separately satisfied; commercial users must not install Community wheels from PyPI.

## Sources

- Qt licensing: https://doc.qt.io/qt-6/licensing.html
- Qt for Python commercial/licensing overview: https://doc.qt.io/qtforpython-6/commercial/index.html
- Qt for Python third-party licenses: https://doc.qt.io/qtforpython-6/licenses.html
- PySide6 PyPI metadata: https://pypi.org/project/PySide6/
