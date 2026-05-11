import pytest
from bot.cards import (
    pool_selection_card,
    confirmation_card,
    validation_error_card,
    success_card,
)
from bot.session_store import get_session_id, set_session_id, clear_session


# --- Card tests ---

def test_pool_selection_card_structure():
    pools = [
        {"pool_id": "pool_1", "pool_name": "Tech Candidates"},
        {"pool_id": "pool_2", "pool_name": "Sales Pipeline"},
    ]
    card = pool_selection_card(pools, candidate_count=42, filename="export.xlsx")
    assert card["type"] == "AdaptiveCard"
    choice_input = next(b for b in card["body"] if b.get("type") == "Input.ChoiceSet")
    assert len(choice_input["choices"]) == 2
    assert choice_input["choices"][0]["value"] == "pool_1"
    assert choice_input["choices"][1]["title"] == "Sales Pipeline"


def test_pool_selection_card_candidate_count_in_body():
    pools = [{"pool_id": "p1", "pool_name": "Pool A"}]
    card = pool_selection_card(pools, candidate_count=15, filename="data.xlsx")
    text_blocks = [b["text"] for b in card["body"] if b.get("type") == "TextBlock"]
    combined = " ".join(text_blocks)
    assert "15" in combined


def test_confirmation_card_facts():
    card = confirmation_card(pool_name="Tech Candidates", candidate_count=30)
    fact_set = next(b for b in card["body"] if b.get("type") == "FactSet")
    titles = [f["title"] for f in fact_set["facts"]]
    assert "Pool" in titles
    assert "Candidates" in titles
    values = [f["value"] for f in fact_set["facts"]]
    assert "Tech Candidates" in values
    assert "30" in values


def test_confirmation_card_has_confirm_and_cancel():
    card = confirmation_card(pool_name="Pool", candidate_count=5)
    action_titles = [a["title"] for a in card["actions"]]
    assert "Confirm" in action_titles
    assert "Cancel" in action_titles


def test_validation_error_card_shows_errors():
    errors = [
        {"row_number": 3, "field": "email", "reason": "Email is required but missing"},
        {"row_number": 5, "field": "first_name", "reason": "First name is required but missing"},
    ]
    card = validation_error_card(errors)
    text_blocks = [b["text"] for b in card["body"] if b.get("type") == "TextBlock"]
    combined = " ".join(text_blocks)
    assert "Row 3" in combined
    assert "Row 5" in combined


def test_validation_error_card_truncates_at_20():
    errors = [
        {"row_number": i, "field": "email", "reason": "Missing"}
        for i in range(25)
    ]
    card = validation_error_card(errors)
    error_blocks = [b for b in card["body"] if b.get("type") == "TextBlock" and "Row" in b.get("text", "")]
    assert len(error_blocks) == 20


def test_success_card_all_succeeded():
    card = success_card(pool_name="Tech Pool", succeeded=50, failed=0)
    text_blocks = [b["text"] for b in card["body"] if b.get("type") == "TextBlock"]
    combined = " ".join(text_blocks)
    assert "successfully" in combined.lower()


def test_success_card_partial_failure():
    card = success_card(pool_name="Tech Pool", succeeded=45, failed=5)
    fact_set = next(b for b in card["body"] if b.get("type") == "FactSet")
    values = {f["title"]: f["value"] for f in fact_set["facts"]}
    assert values["Succeeded"] == "45"
    assert values["Failed"] == "5"


def test_success_card_has_restart_action():
    card = success_card(pool_name="Pool", succeeded=10, failed=0)
    actions = [a["data"]["action"] for a in card["actions"]]
    assert "restart" in actions


# --- Session store tests ---

def test_session_store_set_and_get():
    set_session_id("conv_abc", "session_123")
    assert get_session_id("conv_abc") == "session_123"


def test_session_store_returns_none_for_unknown():
    assert get_session_id("nonexistent_conv") is None


def test_session_store_clear():
    set_session_id("conv_xyz", "session_456")
    clear_session("conv_xyz")
    assert get_session_id("conv_xyz") is None


def test_session_store_overwrite():
    set_session_id("conv_dup", "session_old")
    set_session_id("conv_dup", "session_new")
    assert get_session_id("conv_dup") == "session_new"
