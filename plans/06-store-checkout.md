# 06 — Store, checkout concurrency, PDF receipt — spec FR-2.3, NFR-3, §5.12 (6 pts)

## Tables
`products(product_id PK, tenant_id, club_id, name, category, description)`,
`variants(variant_id PK, product_id, size, color, price_minor, stock int CHECK (stock >= 0), reserved int CHECK (reserved >= 0))`,
`price_changes(variant_id, price_minor, effective_at)` (optional, FR-2.3 scheduled prices),
`discount_codes(code PK, percent)` → seed `WELCOME10 = 10`,
`orders(order_id PK, customer_id, status, request_hash, response JSONB, created_at)`.
The **`CHECK (stock >= 0)`** is a second safety net: even a bug can't make stock negative.

## `POST /audit/v1/checkout` (`services/store.py`)
1. **Validate (400):** order_id/customer_id strings; items 1–10, quantity int 1..10, unique variant_ids; discount_code null or string; payment.token string.
2. **Idempotency:** order_id exists → identical body → stored response with **200**; different → 409 `DUPLICATE_ORDER_ID`. Insert the order row early (status `pending`) inside the transaction so the PK unique constraint also blocks parallel duplicates (catch IntegrityError → re-read → 200/409).
3. Variants exist → else 404 `VARIANT_NOT_FOUND` (`details.variant_id`). Discount: not null and ≠ known code → 400 `INVALID_DISCOUNT_CODE`.
4. **Reserve atomically** (transaction 1): for each item in **sorted variant_id order** (prevents deadlocks):
   ```sql
   UPDATE variants SET stock = stock - :q, reserved = reserved + :q
   WHERE variant_id = :v AND stock >= :q
   ```
   If `rowcount == 0` → rollback whole transaction → 409 `OUT_OF_STOCK`, `details.variant_id`. Commit.
   Why this is safe: Postgres row lock on UPDATE serializes the 20 buyers; the `WHERE stock >= :q` re-check happens after the lock → exactly one wins.
5. **Mock gateway** (`services/payment_gateway.py`, pure-ish): `authorize(token)` → `tok_declined` fails; `capture(auth)` → `tok_capture_fail` fails; else ids `auth_<n>`, `cap_<n>` (n = DB sequence or counter).
   - Declined → transaction 2: `stock += q, reserved -= q`; order `cancelled` → 402 `PAYMENT_DECLINED`.
   - Capture failed → void auth, release the same way → 402 `PAYMENT_CAPTURE_FAILED`.
   - Store the failed response too for idempotent replay.
6. **Success** → transaction 2: `reserved -= q` (stock stays decreased), order `paid`, build response, emit domain event `order.paid` to Redis Stream (`queue.py`, wrap in try/except so Redis down never fails checkout).
7. Totals: `unit_price_minor` = current price; `subtotal` = Σ; `discount_minor = subtotal * 10 // 100` for WELCOME10 else 0; `total = subtotal − discount`; `paid_at` = server time `YYYY-MM-DDTHH:MM:SSZ`.
8. Receipt: `payload` exactly as spec (key set: order_id, customer_id, items[], subtotal_minor, discount_minor, total_minor, currency, paid_at). `signature = sign(order_id, payload)`. `pdf_base64` = base64 of `domain/receipt_pdf.py` output.
9. 201 response exactly as spec.

## `domain/receipt_pdf.py` (fpdf2)
Plain PDF with core font Helvetica: title, order_id, customer, item lines, totals. **Must contain text `order_id` and `PKR 4500.00`** → `f"PKR {total_minor // 100}.{total_minor % 100:02d}"` (no thousands separator). Bytes start with `%PDF`. (Unit-test: decode, check prefix; optionally extract text with `pypdf` in tests only.)

## `GET /audit/v1/inventory/{variant_id}` → `{variant_id, stock, reserved}`; 404 `VARIANT_NOT_FOUND`.

## Order state machine (FR-2.3; not script-graded, good for viva)
`pending → paid → packed → shipped → delivered`; `pending/paid → cancelled`; `paid/packed/shipped/delivered → refunded`. Put allowed transitions in a dict; each transition emits `order.<status>` to the queue. (Only add a route for it if time allows.)

## Test (area `store`)
pytest that resets stock to 1 and fires 20 threads with a `threading.Barrier` → exactly one 201, nineteen 409, stock 0, reserved 0. Plus declined/capture-fail release stock, discount math, idempotent replay, PDF prefix.
