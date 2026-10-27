import json
import threading
from pathlib import Path

import pytest

from core.config import settings
from services.history_service import HistoryService


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ROOT_DIR", str(tmp_path))
    return HistoryService()


def _record(name):
    return {
        "full_name": name,
        "email": [f"{name}@example.com"],
        "education_level": "Bachelor",
        "years_experience": 2,
        "skills_display": {"programming_languages": ["Python"]},
    }


def test_save_record_persists_all_criteria_fields(history):
    breakdown = {"Skills_Score": "7.5", "Overall": "Đạt Yêu Cầu"}
    history.save_record(_record("an"), 6.8, "AI Engineer Intern", breakdown)

    records = history.load_history()
    assert len(records) == 1
    saved = records[0]
    assert saved["candidate_name"] == "an"
    assert saved["total_score"] == 6.8
    assert saved["skills_score"] == "7.5"
    assert saved["overall_status"] == "Đạt Yêu Cầu"
    assert saved["job_title"] == "AI Engineer Intern"


def test_concurrent_saves_keep_every_record_and_leave_no_temp_files(history):
    threads = [
        threading.Thread(target=history.save_record, args=(_record(f"cand{i}"), 5.0, "JD", {}))
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = history.load_history()
    assert len(records) == 8
    assert {r["candidate_name"] for r in records} == {f"cand{i}" for i in range(8)}

    leftovers = [p.name for p in Path(history.data_dir).glob(".history-*.tmp")]
    assert leftovers == []


def test_history_file_stays_valid_json_after_clear(history):
    history.save_record(_record("an"), 9.0, "JD", {})
    history.clear_history()
    assert json.loads(open(history.file_path, encoding="utf-8").read()) == []
