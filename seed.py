import asyncio
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select, text

# Settings
from app.core.config import settings
from app.core.database import Base
from app.core.security import hash_password

# Models
from app.models.user import User
from app.models.category import Category
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.models.coupon import Coupon
from app.models.shipping_provider import ShippingProvider
from app.models.address import Address
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.models.invoice import Invoice

engine = create_async_engine(settings.DATABASE_DIRECT_URL or settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def log(msg: str):
    print(f"  {msg}", flush=True)

async def seed():
    async with Session() as db:
        # ── 1. Admin User ──────────────────────────────────────────────────────
        existing_admin = (await db.execute(
            select(User).where(User.email == "admin@zarijasi.com")
        )).scalar_one_or_none()

        if existing_admin:
            admin_id = existing_admin.id
            log("Admin user already exists — skipping.")
        else:
            admin_id = str(uuid.uuid4())
            admin = User(
                id=admin_id,
                email="admin@zarijasi.com",
                first_name="Admin",
                last_name="User",
                password_hash=hash_password("Admin@1234"),
                role="admin",
                is_verified=True,
                is_active=True,
            )
            db.add(admin)
            log("Created admin user: admin@zarijasi.com / Admin@1234")

        # ── 2. Test Customer ───────────────────────────────────────────────────
        existing_customer = (await db.execute(
            select(User).where(User.email == "customer@zarijasi.com")
        )).scalar_one_or_none()

        if existing_customer:
            customer_id = existing_customer.id
            log("Test customer already exists — skipping.")
        else:
            customer_id = str(uuid.uuid4())
            customer = User(
                id=customer_id,
                email="customer@zarijasi.com",
                first_name="Priya",
                last_name="Sharma",
                phone="9876543210",
                password_hash=hash_password("Customer@1234"),
                role="customer",
                is_verified=True,
                is_active=True,
            )
            db.add(customer)
            log("Created test customer: customer@zarijasi.com / Customer@1234")

        await db.flush()

        # ── 3. Customer Address ───────────────────────────────────────────────
        existing_address = (await db.execute(
            select(Address).where(Address.user_id == customer_id)
        )).scalars().first()

        if existing_address:
            address_id = existing_address.id
            log("Customer address already exists — skipping.")
        else:
            address_id = str(uuid.uuid4())
            address = Address(
                id=address_id,
                user_id=customer_id,
                name="Priya Sharma",
                phone="9876543210",
                line1="Flat 402, Sai Enclave",
                line2="Jubilee Hills",
                city="Hyderabad",
                state="Telangana",
                pincode="500033",
                country="India",
                is_default=True,
            )
            db.add(address)
            log("Created default customer address.")

        # ── 4. Categories ─────────────────────────────────────────────────────
        cat_data = [
            {"name": "Lehengas",       "slug": "lehengas",       "description": "Traditional Indian bridal and festive lehengas"},
            {"name": "Sarees",         "slug": "sarees",         "description": "Handcrafted sarees from across India"},
            {"name": "Kurtis",         "slug": "kurtis",         "description": "Everyday and festive kurtis"},
            {"name": "Anarkali",       "slug": "anarkali",       "description": "Flowy anarkali suits for every occasion"},
            {"name": "Dupattas",       "slug": "dupattas",       "description": "Embroidered and printed dupattas"},
            {"name": "Accessories",    "slug": "accessories",    "description": "Jewellery, bags, and fashion accessories"},
        ]

        categories: dict[str, Category] = {}
        for cat in cat_data:
            existing = (await db.execute(
                select(Category).where(Category.slug == cat["slug"])
            )).scalar_one_or_none()
            if existing:
                categories[cat["slug"]] = existing
            else:
                c = Category(
                    id=str(uuid.uuid4()),
                    name=cat["name"],
                    slug=cat["slug"],
                    description=cat["description"],
                    is_active=True,
                )
                db.add(c)
                categories[cat["slug"]] = c
                log(f"Created category: {cat['name']}")

        await db.flush()

        # ── 5. Products ────────────────────────────────────────────────────────
        products_data = [
            {
                "name": "Crimson Bridal Lehenga",
                "slug": "crimson-bridal-lehenga",
                "category_slug": "lehengas",
                "base_price": 24999,
                "sale_price": 19999,
                "is_featured": True,
                "description": "A stunning crimson lehenga adorned with intricate zari embroidery. Perfect for the modern bride who wants to blend tradition with elegance.",
                "short_description": "Crimson zari embroidery bridal lehenga",
                "brand": "Sabyasachi",
                "images": [
                    "https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&q=80",
                ],
                "variants": [
                    {"size": "S",  "sku": "CRL-S-RED",  "stock_qty": 5},
                    {"size": "M",  "sku": "CRL-M-RED",  "stock_qty": 8},
                    {"size": "L",  "sku": "CRL-L-RED",  "stock_qty": 4},
                    {"size": "XL", "sku": "CRL-XL-RED", "stock_qty": 3},
                ],
            },
            {
                "name": "Royal Blue Banarasi Saree",
                "slug": "royal-blue-banarasi-saree",
                "category_slug": "sarees",
                "base_price": 12499,
                "sale_price": 9999,
                "is_featured": True,
                "description": "A majestic Banarasi saree in deep royal blue with gold zari work. Handwoven by master weavers from Varanasi.",
                "short_description": "Handwoven Banarasi silk saree with gold zari",
                "brand": "Raw Mango",
                "images": [
                    "https://images.unsplash.com/photo-1583391733956-6c78276477e2?w=600&q=80",
                ],
                "variants": [
                    {"size": "Free Size", "sku": "RBS-BLUE-FS", "stock_qty": 12},
                ],
            },
            {
                "name": "Floral Embroidered Kurti",
                "slug": "floral-embroidered-kurti",
                "category_slug": "kurtis",
                "base_price": 3499,
                "sale_price": 2799,
                "is_featured": True,
                "description": "A lightweight cotton kurti with delicate floral embroidery at the neckline and hem. Perfect for casual outings.",
                "short_description": "Cotton kurti with floral embroidery",
                "brand": "Fabindia",
                "images": [
                    "https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&q=80",
                ],
                "variants": [
                    {"size": "S",  "color": "White",  "sku": "FEK-S-WHT",  "stock_qty": 15},
                    {"size": "M",  "color": "White",  "sku": "FEK-M-WHT",  "stock_qty": 20},
                    {"size": "L",  "color": "White",  "sku": "FEK-L-WHT",  "stock_qty": 10},
                    {"size": "S",  "color": "Yellow", "sku": "FEK-S-YLW",  "stock_qty": 8},
                    {"size": "M",  "color": "Yellow", "sku": "FEK-M-YLW",  "stock_qty": 12},
                ],
            },
        ]

        seeded_variants = []
        for pd in products_data:
            existing_product = (await db.execute(
                select(Product).where(Product.slug == pd["slug"])
            )).scalar_one_or_none()

            if existing_product:
                log(f"Product already exists: {pd['name']} — skipping.")
                # Load variants for order seeding
                vars_res = await db.execute(
                    select(ProductVariant).where(ProductVariant.product_id == existing_product.id)
                )
                seeded_variants.extend(vars_res.scalars().all())
                continue

            cat_obj = categories.get(pd["category_slug"])
            if not cat_obj:
                continue

            product = Product(
                id=str(uuid.uuid4()),
                name=pd["name"],
                slug=pd["slug"],
                category_id=cat_obj.id,
                base_price=pd["base_price"],
                sale_price=pd.get("sale_price"),
                is_active=True,
                is_featured=pd.get("is_featured", False),
                description=pd.get("description", ""),
                short_description=pd.get("short_description", ""),
                brand=pd.get("brand", "Zari"),
                tags=[pd["category_slug"]],
            )
            db.add(product)
            await db.flush()

            # Images
            for i, img_url in enumerate(pd.get("images", [])):
                img = ProductImage(
                    id=str(uuid.uuid4()),
                    product_id=product.id,
                    url=img_url,
                    display_order=i,
                    is_primary=(i == 0),
                )
                db.add(img)

            # Variants
            for v in pd.get("variants", []):
                variant = ProductVariant(
                    id=str(uuid.uuid4()),
                    product_id=product.id,
                    size=v.get("size"),
                    color=v.get("color"),
                    sku=v["sku"],
                    stock_qty=v.get("stock_qty", 10),
                    is_active=True,
                )
                db.add(variant)
                seeded_variants.append(variant)

            log(f"Created product: {pd['name']}")

        await db.flush()

        # ── 6. Coupons ────────────────────────────────────────────────────────
        coupons_data = [
            {
                "code": "WELCOME10",
                "type": "percent",
                "value": 10,
                "min_order_amount": 999,
                "max_discount": 500,
                "usage_limit": 1000,
                "description": "10% off on first order (max Rs.500 off)",
            },
            {
                "code": "FLAT500",
                "type": "flat",
                "value": 500,
                "min_order_amount": 2999,
                "description": "Rs.500 flat off on orders above Rs.2999",
            },
        ]

        for cp in coupons_data:
            existing_coupon = (await db.execute(
                select(Coupon).where(Coupon.code == cp["code"])
            )).scalar_one_or_none()

            if existing_coupon:
                log(f"Coupon {cp['code']} already exists — skipping.")
                continue

            coupon = Coupon(
                id=str(uuid.uuid4()),
                code=cp["code"],
                type=cp["type"],
                value=cp["value"],
                min_order_amount=cp.get("min_order_amount"),
                max_discount=cp.get("max_discount"),
                usage_limit=cp.get("usage_limit"),
                is_active=True,
            )
            db.add(coupon)
            log(f"Created coupon: {cp['code']}")

        # ── 7. Shipping Providers ──────────────────────────────────────────────
        providers_data = [
            {
                "name": "Manual (In-House)",
                "slug": "manual",
                "is_active": True,
                "config": {"contact": "logistics@zarijasi.com"},
            },
            {
                "name": "Shiprocket",
                "slug": "shiprocket",
                "is_active": False,
                "config": {},
            },
        ]

        shipping_providers = {}
        for pv in providers_data:
            existing_pv = (await db.execute(
                select(ShippingProvider).where(ShippingProvider.slug == pv["slug"])
            )).scalar_one_or_none()

            if existing_pv:
                shipping_providers[pv["slug"]] = existing_pv
                log(f"Shipping provider {pv['name']} already exists — skipping.")
                continue

            provider = ShippingProvider(
                id=str(uuid.uuid4()),
                name=pv["name"],
                slug=pv["slug"],
                is_active=pv["is_active"],
                config=pv.get("config", {}),
            )
            db.add(provider)
            shipping_providers[pv["slug"]] = provider
            log(f"Created shipping provider: {pv['name']}")

        await db.flush()

        # ── 8. Orders with Various Statuses ────────────────────────────────────
        # Seed 4 orders representing delivered, pending, cancelled, refunded
        if not seeded_variants:
            log("No variants available for order seeding.")
            await db.commit()
            return

        order_status_types = [
            {
                "status": "delivered",
                "payment_status": "paid",
                "subtotal": 19999,
                "discount": 500,
                "shipping_charge": 100,
                "tax_amount": 3509,
                "total": 23098,
                "notes": "Delivered bridal dress",
            },
            {
                "status": "pending",
                "payment_status": "pending",
                "subtotal": 2799,
                "discount": 0,
                "shipping_charge": 50,
                "tax_amount": 503,
                "total": 3352,
                "notes": "Pending payment cotton kurti",
            },
            {
                "status": "cancelled",
                "payment_status": "failed",
                "subtotal": 9999,
                "discount": 0,
                "shipping_charge": 100,
                "tax_amount": 1800,
                "total": 11899,
                "notes": "Customer cancelled order before shipping",
            },
            {
                "status": "refunded",
                "payment_status": "refunded",
                "subtotal": 2799,
                "discount": 0,
                "shipping_charge": 50,
                "tax_amount": 503,
                "total": 3352,
                "notes": "Customer returned product and refunded successfully",
            }
        ]

        manual_provider = shipping_providers.get("manual")
        for i, ost in enumerate(order_status_types):
            existing_order = (await db.execute(
                select(Order).where(Order.notes == ost["notes"])
            )).scalar_one_or_none()

            if existing_order:
                log(f"Order '{ost['notes']}' already exists — skipping.")
                continue

            order_id = str(uuid.uuid4())
            new_order = Order(
                id=order_id,
                user_id=customer_id,
                address_id=address_id,
                subtotal=ost["subtotal"],
                discount=ost["discount"],
                shipping_charge=ost["shipping_charge"],
                tax_amount=ost["tax_amount"],
                total=ost["total"],
                status=ost["status"],
                payment_method="cod" if ost["payment_status"] == "pending" else "razorpay",
                payment_status=ost["payment_status"],
                notes=ost["notes"]
            )
            db.add(new_order)
            await db.flush()

            # Order Item
            selected_var = seeded_variants[i % len(seeded_variants)]
            # Lookup product details
            p_res = await db.execute(select(Product).where(Product.id == selected_var.product_id))
            prod = p_res.scalar_one()

            snapshot = {
                "id": prod.id,
                "name": prod.name,
                "slug": prod.slug,
                "brand": prod.brand,
                "base_price": float(prod.base_price),
                "sale_price": float(prod.sale_price) if prod.sale_price else None,
                "size": selected_var.size,
                "color": selected_var.color,
                "sku": selected_var.sku
            }

            order_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order_id,
                variant_id=selected_var.id,
                product_snapshot=snapshot,
                quantity=1,
                unit_price=ost["subtotal"],
                total_price=ost["subtotal"]
            )
            db.add(order_item)

            # Payment record
            payment = Payment(
                id=str(uuid.uuid4()),
                order_id=order_id,
                provider="cod" if new_order.payment_method == "cod" else "razorpay",
                razorpay_order_id=f"rzp_order_{uuid.uuid4().hex[:12]}" if new_order.payment_method == "razorpay" else None,
                razorpay_payment_id=f"pay_{uuid.uuid4().hex[:14]}" if ost["payment_status"] == "paid" else None,
                amount=ost["total"],
                status=ost["payment_status"]
            )
            db.add(payment)

            # Shipment record (if not pending)
            if ost["status"] != "pending" and manual_provider:
                shipment = Shipment(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    provider_id=manual_provider.id,
                    tracking_number=f"TRK{uuid.uuid4().hex[:10].upper()}",
                    status="delivered" if ost["status"] == "delivered" else ost["status"],
                    shipped_at=datetime.now(timezone.utc) - timedelta(days=2),
                    delivered_at=datetime.now(timezone.utc) - timedelta(days=1) if ost["status"] == "delivered" else None
                )
                db.add(shipment)

            # Invoice record (ONLY generated for delivered orders)
            if ost["status"] == "delivered":
                invoice = Invoice(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    invoice_number=f"INV-2026-{1000 + i}",
                    r2_key=f"invoices/2026/06/INV-2026-{1000 + i}.pdf",
                    r2_url=f"https://ckhsziwgycbamscvyxis.supabase.co/storage/v1/object/sign/invoices/2026/06/INV-2026-{1000 + i}.pdf"
                )
                db.add(invoice)

            log(f"Created seed order: {ost['notes']}")

        await db.commit()
        print("\nSeed completed successfully!", flush=True)

if __name__ == "__main__":
    print("\nZari & Jasi — Database Seed Script", flush=True)
    print("=" * 40, flush=True)
    asyncio.run(seed())
