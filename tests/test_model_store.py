import pytest

import model_store


@pytest.fixture(autouse=True)
def reset_store_cache():
    model_store.reset_cache()
    yield
    model_store.reset_cache()


def test_falls_back_to_baked_model_when_fetch_fails(monkeypatch):
    model_store.reset_cache()
    monkeypatch.setattr(
        model_store.artivity_client,
        "get_active_model",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    model = model_store.get_active_model()
    assert "intercept" in model and model["print_thresholds"]


def test_uses_fetched_model_and_caches(monkeypatch):
    model_store.reset_cache()
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return {
            "id": "v1",
            "intercept": 1000.0,
            "print_thresholds": [0, 50],
            "print_values": [0, 100],
            "color_thresholds": [0, 50],
            "color_values": [0, 200],
        }

    monkeypatch.setattr(model_store.artivity_client, "get_active_model", fake)
    first = model_store.get_active_model()
    second = model_store.get_active_model()
    assert calls["n"] == 1
    assert first["intercept"] == 1000.0
    assert second is first
