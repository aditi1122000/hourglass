import os
import sys
from unittest.mock import MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from streamlit.testing.v1 import AppTest

import auth
import db

APP_PATH = os.path.join(REPO_ROOT, "app.py")
TEST_USER = {"id": "11111111-1111-1111-1111-111111111111", "username": "alice"}


def _mock_db(monkeypatch):
    monkeypatch.setattr(db, "get_user_by_username", MagicMock(return_value=None))
    monkeypatch.setattr(db, "create_user", MagicMock(return_value={"id": TEST_USER["id"], "username": TEST_USER["username"]}))
    monkeypatch.setattr(auth, "verify_password", MagicMock(return_value=True))
    monkeypatch.setattr(db, "get_unredeemed_token_count", MagicMock(return_value=0))
    monkeypatch.setattr(db, "get_categories", MagicMock(return_value=[]))
    monkeypatch.setattr(db, "get_logs_for_date", MagicMock(return_value=[]))
    monkeypatch.setattr(db, "get_all_logs", MagicMock(return_value=[]))
    monkeypatch.setattr(db, "get_total_token_count", MagicMock(return_value=0))
    monkeypatch.setattr(db, "get_redemption_count", MagicMock(return_value=0))


def test_logged_out_shows_login_form_not_authenticated_view(monkeypatch):
    _mock_db(monkeypatch)
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=15)

    assert at.exception == []
    assert "user" not in at.session_state
    assert [w.label for w in at.text_input] == ["Username", "Password"]
    assert any("Log in" in (b.label or "") for b in at.button)
    assert len(at.segmented_control) == 0
    assert not any(b.label == "Log out" for b in at.button)


def test_logged_in_shows_authenticated_view_not_login_form(monkeypatch):
    _mock_db(monkeypatch)
    at = AppTest.from_file(APP_PATH)
    at.session_state["user"] = TEST_USER
    at.run(timeout=15)

    assert at.exception == []
    assert "user" in at.session_state
    labels = [w.label for w in at.text_input]
    assert "Username" not in labels
    assert "Password" not in labels
    assert any(b.label == "Log out" for b in at.button)
    assert not any("Log in" in (b.label or "") for b in at.button)
    assert len(at.segmented_control) == 1
    assert at.segmented_control[0].value == "🏠 Today"


def test_login_submit_transitions_cleanly_to_authenticated_view(monkeypatch):
    _mock_db(monkeypatch)
    monkeypatch.setattr(
        db,
        "get_user_by_username",
        MagicMock(return_value={"id": TEST_USER["id"], "username": TEST_USER["username"], "password_hash": "x"}),
    )
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=15)

    at.text_input[0].input("alice")
    at.text_input[1].input("secret")
    at.run(timeout=15)
    submit_btn = next(b for b in at.button if "Log in" in (b.label or ""))
    submit_btn.click().run(timeout=15)

    assert at.exception == []
    assert "user" in at.session_state
    labels = [w.label for w in at.text_input]
    assert "Username" not in labels
    assert "Password" not in labels
    assert not any("Log in" in (b.label or "") for b in at.button)
    assert len(at.segmented_control) == 1


def test_logout_transitions_cleanly_back_to_login_form(monkeypatch):
    _mock_db(monkeypatch)
    at = AppTest.from_file(APP_PATH)
    at.session_state["user"] = TEST_USER
    at.run(timeout=15)

    logout_btn = next(b for b in at.button if b.label == "Log out")
    logout_btn.click().run(timeout=15)

    assert at.exception == []
    assert "user" not in at.session_state
    assert [w.label for w in at.text_input] == ["Username", "Password"]
    assert any("Log in" in (b.label or "") for b in at.button)
    assert len(at.segmented_control) == 0


def test_today_is_default_landing_view_with_insights_and_redeem_reachable(monkeypatch):
    _mock_db(monkeypatch)
    at = AppTest.from_file(APP_PATH)
    at.session_state["user"] = TEST_USER
    at.run(timeout=15)

    # Today lands by default: its own hero metrics show, Insights' metrics do not.
    assert at.segmented_control[0].value == "🏠 Today"
    assert [m.label for m in at.metric] == ["Productive today", "🎟️ Tokens"]

    at.segmented_control[0].set_value("📊 Insights").run(timeout=15)
    assert at.exception == []
    assert [m.label for m in at.metric] == [
        "Day streak",
        "Total hours logged",
        "Tokens earned",
        "Trees grown",
    ]

    at.segmented_control[0].set_value("🎁 Redeem").run(timeout=15)
    assert at.exception == []
    assert not at.metric
