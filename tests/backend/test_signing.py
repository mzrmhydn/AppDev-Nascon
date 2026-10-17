# Spec Appendix A test vectors for signing.py (§5.3, §5.10).
from app.signing import canonical, lots_key, sign


def test_signature_vector_1():
    payload = {"team_id": "t1", "event_type": "goal"}
    assert canonical(payload) == '{"event_type":"goal","team_id":"t1"}'
    assert sign("evt-1", payload, salt="demo-salt") == \
        "972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501"


def test_canonical_keeps_unicode_and_ints():
    assert canonical({"b": 1, "a": "Ali Khan ✓"}) == '{"a":"Ali Khan ✓","b":1}'


def test_lots_vector_2():
    assert lots_key(42, "lg-1", "t1") == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"
    assert lots_key(42, "lg-1", "t3") == "c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028"
