# tests/test_llm_handler.py
import pytest
from app import llm_handler

def test_parse_single_transaction(mocker):
    """Tests ADD-TXN-01: 500 for pizza from Jupiter"""
    # Mock the API response
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"transactions": [{"action": "add_transaction", "data": {"amount": 500, "note": "pizza", "wallet": "Jupiter"}}]}'}}]
    }
    mocker.patch('requests.post', return_value=mock_response)

    actions = llm_handler.parse_message("500 for pizza from Jupiter")
    
    assert len(actions) == 1
    assert actions[0]['action'] == 'add_transaction'
    assert actions[0]['data']['amount'] == 500
    assert actions[0]['data']['wallet'] == 'Jupiter'

def test_parse_multi_transaction(mocker):
    """Tests ADD-TXN-10: 50 for chai, 100 for samosa"""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"transactions": [{"action": "add_transaction", "data": {"amount": 50, "note": "chai"}}, {"action": "add_transaction", "data": {"amount": 100, "note": "samosa"}}]}'}}]
    }
    mocker.patch('requests.post', return_value=mock_response)

    actions = llm_handler.parse_message("50 for chai, 100 for samosa")

    assert len(actions) == 2
    assert actions[0]['data']['amount'] == 50
    assert actions[1]['data']['amount'] == 100

def test_parse_ambiguous_query(mocker):
    """Tests an ambiguous query that should ask for clarification"""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"transactions": [{"action": "clarify", "data": {"reply": "Bhai, main samjha nahi..."}}]}'}}]
    }
    mocker.patch('requests.post', return_value=mock_response)

    actions = llm_handler.parse_message("delete it")
    
    assert actions[0]['action'] == 'clarify'
    assert "samjha nahi" in actions[0]['data']['reply']