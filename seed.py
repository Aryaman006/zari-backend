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
from app.core.security import hash_password  # Uses SHA256 + bcrypt, matches verify_password

# Models
from app.models.user import User
from app.models.category import Category
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.models.coupon import Coupon
from app.models.shipping_provider import ShippingProvider

engine = create_async_engine(settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def log(msg: str):
    print(f"  {msg}", flush=True)


async def seed():
    async with Session() as db:
        # ── Admin User ─────────────────────────────────────────────────────────
        existing_admin = (await db.execute(
            select(User).where(User.email == "admin@zarijasi.com")
        )).scalar_one_or_none()

        if existing_admin:
            log("Admin user already exists — skipping.")
        else:
            admin = User(
                id=str(uuid.uuid4()),
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

        # ── Test Customer ──────────────────────────────────────────────────────
        existing_customer = (await db.execute(
            select(User).where(User.email == "customer@zarijasi.com")
        )).scalar_one_or_none()

        if existing_customer:
            log("Test customer already exists — skipping.")
        else:
            customer = User(
                id=str(uuid.uuid4()),
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

        # ── Categories ──────────────────────────────────────────────────────────
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

        # ── Products ────────────────────────────────────────────────────────────
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
            {
                "name": "Gold Zari Dupatta",
                "slug": "gold-zari-dupatta",
                "category_slug": "dupattas",
                "base_price": 1999,
                "sale_price": None,
                "is_featured": False,
                "description": "A luxurious pure chiffon dupatta with heavy gold zari border. Pair with any suit to instantly elevate the look.",
                "short_description": "Pure chiffon dupatta with gold zari border",
                "images": [
                    "https://images.unsplash.com/photo-1596609548086-85bbf8ddb6b9?w=600&q=80",
                ],
                "variants": [
                    {"size": "Free Size", "color": "Gold",  "sku": "GZD-GOLD-FS",  "stock_qty": 25},
                    {"size": "Free Size", "color": "Silver","sku": "GZD-SLV-FS",   "stock_qty": 18},
                ],
            },
            {
                "name": "Rose Pink Anarkali",
                "slug": "rose-pink-anarkali",
                "category_slug": "anarkali",
                "base_price": 7999,
                "sale_price": 5999,
                "is_featured": True,
                "description": "A floor-length rose pink anarkali with intricate sequin and thread embroidery. Includes matching dupatta.",
                "short_description": "Sequin embroidered rose pink anarkali with dupatta",
                "images": [
                    "https://images.unsplash.com/photo-1585487000160-6ebcfceb0d03?w=600&q=80",
                ],
                "variants": [
                    {"size": "S",  "sku": "RPA-S-PINK",  "stock_qty": 6},
                    {"size": "M",  "sku": "RPA-M-PINK",  "stock_qty": 9},
                    {"size": "L",  "sku": "RPA-L-PINK",  "stock_qty": 7},
                ],
            },
            {
                "name": "Meenakari Jhumkas",
                "slug": "meenakari-jhumkas",
                "category_slug": "accessories",
                "base_price": 1499,
                "sale_price": 999,
                "is_featured": False,
                "description": "Handcrafted meenakari jhumkas with vibrant enamel work and pearl drops. A timeless traditional design.",
                "short_description": "Handcrafted meenakari jhumkas with pearl drops",
                "images": [
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=600&q=80",
                ],
                "variants": [
                    {"size": "One Size", "sku": "MJK-MULTI-OS", "stock_qty": 30},
                ],
            },
            {
                "name": "Emerald Green Georgette Saree",
                "slug": "emerald-green-georgette-saree",
                "category_slug": "sarees",
                "base_price": 8999,
                "sale_price": 7499,
                "is_featured": False,
                "description": "A shimmering emerald green georgette saree with intricate sequin border and pallu. Perfect for evening events.",
                "short_description": "Sequin border emerald georgette saree",
                "images": [
                    "https://images.unsplash.com/photo-1594938298603-c8148c4b2f47?w=600&q=80",
                ],
                "variants": [
                    {"size": "Free Size", "sku": "EGS-GREEN-FS", "stock_qty": 0},  # Out of stock
                ],
            },
            {
                "name": "Navy Block Print Kurti Set",
                "slug": "navy-block-print-kurti-set",
                "category_slug": "kurtis",
                "base_price": 4999,
                "sale_price": 3799,
                "is_featured": False,
                "description": "A beautiful set of navy blue kurti with matching palazzo and dupatta featuring traditional Rajasthani block print patterns.",
                "short_description": "Rajasthani block print kurti-palazzo-dupatta set",
                "images": [
                    "https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&q=80",
                ],
                "variants": [
                    {"size": "S",  "sku": "NBPKS-S-NAVY",  "stock_qty": 3},  # Low stock
                    {"size": "M",  "sku": "NBPKS-M-NAVY",  "stock_qty": 2},  # Low stock
                    {"size": "L",  "sku": "NBPKS-L-NAVY",  "stock_qty": 1},  # Low stock
                ],
            },
        ]

        for pd in products_data:
            existing_product = (await db.execute(
                select(Product).where(Product.slug == pd["slug"])
            )).scalar_one_or_none()

            if existing_product:
                log(f"Product already exists: {pd['name']} — skipping.")
                continue

            cat_obj = categories.get(pd["category_slug"])
            if not cat_obj:
                log(f"Category not found for {pd['name']} — skipping.")
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

            log(f"Created product: {pd['name']}")

        await db.flush()

        # ── Coupons ─────────────────────────────────────────────────────────────
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
            {
                "code": "ZARI20",
                "type": "percent",
                "value": 20,
                "min_order_amount": 4999,
                "max_discount": 2000,
                "expires_at": datetime(2026, 12, 31, tzinfo=timezone.utc),
                "description": "20% off on orders above Rs.4999",
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
                expires_at=cp.get("expires_at"),
                is_active=True,
            )
            db.add(coupon)
            log(f"Created coupon: {cp['code']}")

        # ── Shipping Providers ─────────────────────────────────────────────────
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
            {
                "name": "Delhivery",
                "slug": "delhivery",
                "is_active": False,
                "config": {},
            },
        ]

        for pv in providers_data:
            existing_pv = (await db.execute(
                select(ShippingProvider).where(ShippingProvider.slug == pv["slug"])
            )).scalar_one_or_none()

            if existing_pv:
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
            log(f"Created shipping provider: {pv['name']}")

        await db.commit()
        print("\nSeed completed successfully!", flush=True)


if __name__ == "__main__":
    print("\nZari & Jasi — Database Seed Script", flush=True)
    print("=" * 40, flush=True)
    asyncio.run(seed())
