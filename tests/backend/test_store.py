# Store tests (spec §5.12, NFR-3): 20-buyer burst, payment failures release stock, discount, replay, PDF.
import base64
import io
import threading

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.domain.receipt_pdf import build_receipt_pdf, money
from app.main import app
from app.signing import sign

M = "var-jersey-001-M"
L = "var-jersey-001-L"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def reset(client, m=1, l_=5):
    assert client.post("/audit/v1/reset", json={"stock": {M: m, L: l_}}).status_code == 200


def order(order_id, token="tok_success", items=None, code=None, customer="cust-001"):
    return {"order_id": order_id, "customer_id": customer,
            "items": items or [{"variant_id": M, "quantity": 1}],
            "discount_code": code, "payment": {"token": token}}


def stock(client, variant=M):
    return client.get(f"/audit/v1/inventory/{variant}").json()


def test_twenty_buyers_exactly_one_wins(client):
    reset(client, m=1)
    barrier = threading.Barrier(20)
    codes = []
    lock = threading.Lock()

    def buy(n):
        barrier.wait()
        r = client.post("/audit/v1/checkout", json=order(f"burst-{n}"))
        with lock:
            codes.append(r.status_code)

    threads = [threading.Thread(target=buy, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [201] + [409] * 19
    assert stock(client) == {"variant_id": M, "stock": 0, "reserved": 0}


def test_success_body_signature_and_pdf(client):
    reset(client)
    r = client.post("/audit/v1/checkout", json=order("ord-001"))
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "paid" and data["total_minor"] == 450000
    assert data["payment"] == {"authorization_id": "auth_1", "capture_id": "cap_1", "state": "captured"}
    payload = data["receipt"]["payload"]
    assert set(payload) == {"order_id", "customer_id", "items", "subtotal_minor", "discount_minor",
                            "total_minor", "currency", "paid_at"}
    assert data["receipt"]["signature"] == sign("ord-001", payload)
    pdf = base64.b64decode(data["receipt"]["pdf_base64"])
    assert pdf.startswith(b"%PDF")
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "ord-001" in text and "PKR 4500.00" in text
    assert stock(client) == {"variant_id": M, "stock": 0, "reserved": 0}


def test_idempotent_replay_and_duplicate(client):
    reset(client, m=3)
    first = client.post("/audit/v1/checkout", json=order("ord-r"))
    again = client.post("/audit/v1/checkout", json=order("ord-r"))
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    assert stock(client)["stock"] == 2  # no second reservation
    r = client.post("/audit/v1/checkout", json=order("ord-r", customer="someone-else"))
    assert (r.status_code, r.json()["error"]["code"]) == (409, "DUPLICATE_ORDER_ID")


@pytest.mark.parametrize("token,code", [("tok_declined", "PAYMENT_DECLINED"),
                                        ("tok_capture_fail", "PAYMENT_CAPTURE_FAILED")])
def test_payment_failures_release_stock(client, token, code):
    reset(client, m=1)
    r = client.post("/audit/v1/checkout", json=order("ord-f", token=token))
    assert (r.status_code, r.json()["error"]["code"]) == (402, code)
    assert stock(client) == {"variant_id": M, "stock": 1, "reserved": 0}
    replay = client.post("/audit/v1/checkout", json=order("ord-f", token=token))
    assert replay.status_code == 402 and replay.json() == r.json()
    assert client.post("/audit/v1/checkout", json=order("ord-ok")).status_code == 201  # buyable again


def test_discount_and_multi_item(client):
    reset(client, m=2, l_=5)
    items = [{"variant_id": L, "quantity": 3}, {"variant_id": M, "quantity": 1}]
    data = client.post("/audit/v1/checkout", json=order("ord-d", items=items, code="WELCOME10")).json()
    assert data["subtotal_minor"] == 1800000
    assert data["discount_minor"] == 180000 and data["total_minor"] == 1620000
    assert stock(client, L)["stock"] == 2


def test_validation_order(client):
    reset(client)
    r = client.post("/audit/v1/checkout", json=order("ord-v", items=[{"variant_id": "nope", "quantity": 1}],
                                                     code="BOGUS"))
    assert (r.status_code, r.json()["error"]["code"]) == (404, "VARIANT_NOT_FOUND")
    r = client.post("/audit/v1/checkout", json=order("ord-v", code="BOGUS"))
    assert (r.status_code, r.json()["error"]["code"]) == (400, "INVALID_DISCOUNT_CODE")
    r = client.post("/audit/v1/checkout", json=order("ord-v", items=[{"variant_id": M, "quantity": 11}]))
    assert r.status_code == 400 and r.json()["error"]["details"]["fields"] == ["items"]
    r = client.post("/audit/v1/checkout", json=order("ord-v", items=[{"variant_id": M, "quantity": 1}] * 2))
    assert r.status_code == 400
    r = client.post("/audit/v1/checkout", json={"order_id": "bad|id"})
    assert set(r.json()["error"]["details"]["fields"]) == {"order_id", "customer_id", "items", "payment"}
    assert client.post("/audit/v1/checkout", content=b"{oops").status_code == 400
    assert client.get("/audit/v1/inventory/nope").status_code == 404


def test_out_of_stock_stores_nothing(client):
    reset(client, m=0)
    r = client.post("/audit/v1/checkout", json=order("ord-o"))
    assert (r.status_code, r.json()["error"]) == (409, {"code": "OUT_OF_STOCK", "message": r.json()["error"]["message"],
                                                        "details": {"variant_id": M}})
    reset_stock = client.post("/audit/v1/reset", json={"stock": {M: 1}})
    assert reset_stock.status_code == 200
    assert client.post("/audit/v1/checkout", json=order("ord-o")).status_code == 201  # same id runs again


def test_script_tags_are_plain_data(client):
    reset(client)
    r = client.post("/audit/v1/checkout", json=order("ord-x", customer="<script>alert(\"x\")</script> é ✓"))
    assert r.status_code == 201
    assert r.json()["receipt"]["payload"]["customer_id"] == "<script>alert(\"x\")</script> é ✓"


def test_api_twin_needs_login(client):
    reset(client)
    assert client.post("/api/v1/checkout", json=order("ord-api")).status_code == 401
    token = client.post("/api/v1/auth/login", json={"email": "viewer@nascon.test",
                                                    "password": "Nascon@26"}).json()["token"]
    r = client.post("/api/v1/checkout", json=order("ord-api"), headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201


def test_money_format():
    assert money(450000) == "PKR 4500.00" and money(5) == "PKR 0.05"
    pdf = build_receipt_pdf({"order_id": "o", "customer_id": "ü✓", "paid_at": "x", "items": [],
                             "subtotal_minor": 0, "discount_minor": 0, "total_minor": 0})
    assert pdf.startswith(b"%PDF")
