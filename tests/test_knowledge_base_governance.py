import importlib.util
from pathlib import Path


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_knowledge_base_update.py"
)
_SPEC = importlib.util.spec_from_file_location("check_knowledge_base_update", _SCRIPT_PATH)
kb_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(kb_check)


def test_code_changes_require_knowledge_base_review():
    changed = ["src/database.py", "tests/test_database.py"]

    assert kb_check.changed_files_requiring_kb_review(changed) == ["src/database.py"]
    assert not kb_check.has_kb_audit(changed)


def test_knowledge_base_log_satisfies_audit():
    changed = [
        "src/database.py",
        "knowledge_base/wiki/data/nhl-api-shot-events.md",
        "knowledge_base/log.md",
    ]

    assert kb_check.has_kb_audit(changed)


def test_test_only_and_local_settings_do_not_require_review():
    changed = ["tests/test_database.py", ".claude/settings.local.json"]

    assert kb_check.changed_files_requiring_kb_review(changed) == []
