from pathlib import Path

from PySide6.QtCore import Qt

from rfinance.application.market_csv_import import MarketCSVImportService
from rfinance.application.observation_review import ObservationReviewService
from rfinance.storage.database import Database
from rfinance.storage.repositories.data_ingestion import DataIngestionRepository
from rfinance.ui.observation_review_page import ObservationReviewPage


def test_observation_review_page_rejects_with_evidence_and_preserves_raw_record(
    qtbot, tmp_path: Path
) -> None:
    database = Database.open(tmp_path / "observation-review.sqlite3")
    database.upgrade()
    data_directory = tmp_path / "rfinance-data"
    csv_file = tmp_path / "market.csv"
    csv_file.write_text(
        "instrument_id,observed_at,currency,close\n"
        "IDX:BBCA,2026-11-21T09:00:00+07:00,IDR,9500\n",
        encoding="utf-8",
    )
    evidence_file = tmp_path / "price-evidence.txt"
    evidence_file.write_text(
        "Manually reviewed the user-supplied source record.",
        encoding="utf-8",
    )

    importer = MarketCSVImportService(
        DataIngestionRepository(database.sessions),
        data_directory=data_directory,
    )
    importer.import_market_csv(csv_file, source_name="User-supplied evidence")
    service = ObservationReviewService(
        database.sessions,
        data_directory=data_directory,
    )
    page = ObservationReviewPage(service)
    qtbot.addWidget(page)
    page.show()

    try:
        assert page.observation_table.rowCount() == 1
        observation_id = page.observation_table.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert isinstance(observation_id, str)
        assert page.observation_table.item(0, 4).text() == "UNVERIFIED"
        assert page.observation_table.item(0, 5).text() == "UNVERIFIED"

        page.reviewer_input.setText("Local operator")
        page.notes_input.setText("Checked the supplied source document.")
        page.evidence_path_input.setText(str(evidence_file))

        qtbot.mouseClick(page.verify_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: (
                not page.is_busy
                and page.status_label.text().startswith("Observation review failed:")
            ),
            timeout=10000,
        )
        assert "instrument identity must be VERIFIED" in page.status_label.text()
        assert service.effective_quality(observation_id) == "UNVERIFIED"
        assert page.history_table.rowCount() == 0

        qtbot.mouseClick(page.reject_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: (
                not page.is_busy
                and page.status_label.text().startswith("Review recorded:")
            ),
            timeout=10000,
        )

        assert service.effective_quality(observation_id) == "REJECTED"
        assert page.observation_table.item(0, 4).text() == "UNVERIFIED"
        assert page.observation_table.item(0, 5).text() == "REJECTED"
        assert page.history_table.rowCount() == 1
        assert "SHA-256:" in page.history_table.item(0, 4).toolTip()

        with database.sessions() as session:
            from sqlalchemy import select

            from rfinance.storage.models.data_ingestion import MarketObservationRecord
            from rfinance.storage.models.observation_review import ObservationReviewEventRecord

            raw_record = session.get(MarketObservationRecord, observation_id)
            events = session.scalars(select(ObservationReviewEventRecord)).all()
            assert raw_record is not None
            assert raw_record.quality_status == "UNVERIFIED"
            assert len(events) == 1
            archived = data_directory / events[0].evidence_reference
            assert archived.is_file()
            assert events[0].evidence_sha256
    finally:
        page.close()
        database.close()
