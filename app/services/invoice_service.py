"""
Invoice service — generates PDF invoices using WeasyPrint + Jinja2
and stores them via the active storage backend (local or Cloudflare R2).
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.invoice import Invoice
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

# Jinja2 template environment
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def _generate_invoice_number(order: Order) -> str:
    """Generate sequential invoice number: ZJ-YYYY-NNNNNN"""
    year = datetime.now(timezone.utc).year
    short_id = order.id.replace("-", "")[:6].upper()
    return f"ZJ-{year}-{short_id}"


class InvoiceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)

    async def generate_invoice(self, order_id: str) -> Invoice:
        """
        Generate a PDF invoice for the given order:
        1. Load order with all relations
        2. Render Jinja2 HTML template
        3. Convert to PDF via WeasyPrint (or fallback HTML on Windows)
        4. Upload via storage backend (local or R2)
        5. Save Invoice record to DB
        """
        from sqlalchemy import select
        from app.models.invoice import Invoice as InvoiceModel

        # Check if invoice already exists
        existing = (
            await self.session.execute(
                select(InvoiceModel).where(InvoiceModel.order_id == order_id)
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        order = await self.order_repo.get_by_id_with_relations(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        invoice_number = _generate_invoice_number(order)

        # ── Build template context ───────────────────────────────────────────
        taxable_amount = float(order.subtotal) - float(order.discount)
        cgst_rate_pct = settings.CGST_RATE * 100
        sgst_rate_pct = settings.SGST_RATE * 100
        cgst_amount = taxable_amount * settings.CGST_RATE
        sgst_amount = taxable_amount * settings.SGST_RATE

        items = []
        for item in order.items:
            snapshot = item.product_snapshot or {}
            items.append({
                "product_name": snapshot.get("product_name", "Product"),
                "sku": snapshot.get("sku", "N/A"),
                "size": snapshot.get("size"),
                "color": snapshot.get("color"),
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price),
            })

        addr = order.address
        context = {
            "invoice_number": invoice_number,
            "invoice_date": datetime.now(timezone.utc).strftime("%d %B %Y"),
            "order_number": order.id[:8].upper(),
            "order_date": order.created_at.strftime("%d %B %Y"),
            "business_name": settings.BUSINESS_NAME,
            "business_address": settings.BUSINESS_ADDRESS,
            "gstin": settings.GSTIN,
            "customer_name": f"{order.user.first_name} {order.user.last_name}" if order.user else "Customer",
            "customer_phone": addr.phone if addr else "",
            "billing_address": addr,
            "shipping_address": addr,
            "payment_method": order.payment_method.upper().replace("_", " "),
            "payment_status": order.payment_status,
            "razorpay_payment_id": order.payment.razorpay_payment_id if order.payment else None,
            "items": items,
            "subtotal": float(order.subtotal),
            "discount": float(order.discount),
            "coupon_code": order.coupon.code if order.coupon else None,
            "shipping_charge": float(order.shipping_charge),
            "taxable_amount": taxable_amount,
            "cgst_rate": cgst_rate_pct,
            "sgst_rate": sgst_rate_pct,
            "cgst_amount": cgst_amount,
            "sgst_amount": sgst_amount,
            "tax_amount": cgst_amount + sgst_amount,
            "total": float(order.total),
        }

        # ── Render HTML ──────────────────────────────────────────────────────
        template = jinja_env.get_template("invoice.html")
        html_content = template.render(**context)

        # ── Generate PDF (or HTML fallback) ───────────────────────────────────
        now = datetime.now(timezone.utc)
        storage_key = f"invoices/{now.year}/{now.month:02d}/{invoice_number}.pdf"
        file_content, file_content_type = self._generate_document(html_content, storage_key)

        # ── Upload via storage backend ─────────────────────────────────────
        stored_url: Optional[str] = None
        try:
            stored_url = await storage_service.upload_bytes(
                key=storage_key,
                data=file_content,
                content_type=file_content_type,
                bucket="invoices",
            )
        except Exception as e:
            logger.warning(f"Failed to store invoice [{storage_service.backend_name}]: {e}")

        # ── Persist Invoice record ────────────────────────────────────────────
        invoice = InvoiceModel(
            order_id=order_id,
            invoice_number=invoice_number,
            gstin=settings.GSTIN,
            r2_key=storage_key,
            r2_url=stored_url,
        )
        self.session.add(invoice)
        await self.session.flush()
        await self.session.refresh(invoice)

        logger.info(f"Invoice {invoice_number} generated for order {order_id}")
        return invoice

    def _generate_document(self, html: str, key: str) -> tuple[bytes, str]:
        """
        Try to generate a PDF using WeasyPrint.
        Falls back to returning the HTML itself if WeasyPrint is unavailable.
        Returns (content_bytes, content_type).
        """
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf()
            logger.info("Invoice PDF generated via WeasyPrint")
            return pdf_bytes, "application/pdf"
        except ImportError:
            logger.warning(
                "WeasyPrint not available (missing system dependencies on this platform). "
                "Saving invoice as HTML instead."
            )
        except Exception as e:
            logger.warning(f"WeasyPrint PDF generation failed: {e}. Saving as HTML.")

        # HTML fallback — change storage key extension too
        return html.encode("utf-8"), "text/html"

    async def get_download_url(self, invoice: Invoice, expires_in: int = 3600) -> str:
        """
        Generate a URL to access/download an invoice document.
        For local storage: returns the direct public URL.
        For others: returns a presigned download URL with bucket="invoices".
        """
        if not invoice.r2_key:
            raise ValueError("Invoice has no storage key.")
        # For local storage, r2_url is already the public URL
        if invoice.r2_url and storage_service.backend_name == "local":
            return invoice.r2_url
        return await storage_service.generate_download_url(
            invoice.r2_key, expires_in=expires_in, bucket="invoices"
        )
