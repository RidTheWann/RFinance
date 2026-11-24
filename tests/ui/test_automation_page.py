# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from pathlib import Path

from sqlalchemy import text

from rfinance.application.automation import AutomationService
from rfinance.domain.automation.jobs import JobDefinition
from rfinance.storage.database import Database
from rfinance.ui.automation_page import AutomationPage


def test_automation_page_runs_registered_job_off_ui_thread(qtbot, tmp_path: Path) -> None:
    database = Database.open(tmp_path / "automation-page.sqlite3")
    database.upgrade()
    definition = JobDefinition(
        job_id="LOCAL_JOB",
        display_name="Local job",
        description="Registered local job",
    )
    service = AutomationService(
        database.sessions,
        definitions={definition.job_id: definition},
        operations={definition.job_id: lambda: "completed locally"},
    )
    service.register_jobs()
    try:
        page = AutomationPage(service)
        qtbot.addWidget(page)
        page.show()

        assert page.jobs_table.rowCount() == 1
        page.run_selected()
        qtbot.waitUntil(
            lambda: not page.is_busy and "SUCCEEDED" in page.status_label.text(),
            timeout=30000,
        )
        qtbot.wait(200)
        assert page.runs_table.rowCount() == 2
        assert page.run_button.isEnabled()
    finally:
        database.close()


def test_automation_run_targets_job_when_a_non_id_column_is_clicked(qtbot, tmp_path: Path) -> None:
    """Clicking the Name/Enabled/Schedule column must still run the right job."""

    database = Database.open(tmp_path / "automation-page-column.sqlite3")
    database.upgrade()
    definition = JobDefinition(
        job_id="LOCAL_JOB",
        display_name="Local job",
        description="Registered local job",
    )
    service = AutomationService(
        database.sessions,
        definitions={definition.job_id: definition},
        operations={definition.job_id: lambda: "completed locally"},
    )
    service.register_jobs()
    try:
        page = AutomationPage(service)
        qtbot.addWidget(page)
        page.show()

        page.jobs_table.setCurrentCell(0, 1)  # display name, not the id column
        page.run_selected()
        qtbot.waitUntil(
            lambda: not page.is_busy and "SUCCEEDED" in page.status_label.text(),
            timeout=30000,
        )

        with database.engine.connect() as connection:
            job_ids = connection.execute(
                text("SELECT job_id FROM automation_runs ORDER BY started_at_utc")
            ).fetchall()
        assert [row[0] for row in job_ids][-1] == "LOCAL_JOB"
    finally:
        database.close()
