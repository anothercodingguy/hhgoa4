"""
Unit tests for TigerGraph Graph Engine and In-Memory Index.
"""
import pytest
from src.tigergraph_engine.in_memory_graph import InMemoryTigerGraph

def test_graph_initialization():
    graph = InMemoryTigerGraph()
    assert not graph.is_loaded
    assert len(graph.customers) == 0
    assert len(graph.cards) == 0

def test_device_neighbors():
    graph = InMemoryTigerGraph()
    # Add synthetic device and cards
    dev_prof = "Samsung SM-G935F | Android 7.0 | chrome 62.0 | 1920x1080"
    graph.device_to_cards[dev_prof] = {"C00123-K1", "C00456-K1", "C00789-K2"}
    
    neighbors = graph.get_device_neighbors(dev_prof, exclude_card="C00123-K1")
    assert len(neighbors) == 2
    assert "C00123-K1" not in neighbors
    assert "C00456-K1" in neighbors
    assert "C00789-K2" in neighbors

def test_card_testing_detection():
    graph = InMemoryTigerGraph()
    card_id = "C99999-K1"
    
    # 3 small transactions followed by a larger one
    graph.transactions["T1"] = {"txn_id": "T1", "card_id": card_id, "amount": 1.50, "channel": "online", "ts": "2016-11-01 10:00:00"}
    graph.transactions["T2"] = {"txn_id": "T2", "card_id": card_id, "amount": 2.20, "channel": "online", "ts": "2016-11-01 10:15:00"}
    graph.transactions["T3"] = {"txn_id": "T3", "card_id": card_id, "amount": 0.99, "channel": "online", "ts": "2016-11-01 10:30:00"}
    graph.transactions["T4"] = {"txn_id": "T4", "card_id": card_id, "amount": 250.00, "channel": "online", "ts": "2016-11-01 10:45:00"}
    
    graph.card_txns[card_id] = ["T1", "T2", "T3", "T4"]
    
    detected, affected, exposure = graph.detect_card_testing(card_id, "T4")
    assert detected is True
    assert len(affected) >= 3
    assert exposure >= 250.0
