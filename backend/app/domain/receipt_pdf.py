# Server-side PDF receipt bytes (FR-2.3, spec §5.12). Pure: receipt payload dict in, PDF bytes out.
from fpdf import FPDF


def money(minor):
    """450000 -> "PKR 4500.00" (major units, 2 decimals, no thousands separator)."""
    return f"PKR {minor // 100}.{minor % 100:02d}"


def latin1(text):
    # Core PDF fonts only cover Latin-1; replace anything else so odd customer ids never cause a 500.
    return str(text).encode("latin-1", "replace").decode("latin-1")


def build_receipt_pdf(payload):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Order receipt", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 7, latin1(f"Order: {payload['order_id']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, latin1(f"Customer: {payload['customer_id']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, latin1(f"Paid at: {payload['paid_at']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    for item in payload["items"]:
        line = f"{item['variant_id']}  x{item['quantity']}  @ {money(item['unit_price_minor'])}"
        pdf.cell(0, 7, latin1(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.cell(0, 7, f"Subtotal: {money(payload['subtotal_minor'])}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Discount: {money(payload['discount_minor'])}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Total: {money(payload['total_minor'])}", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
