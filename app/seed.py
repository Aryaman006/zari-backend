"""
Seed script — populates the database with initial data for development.

Usage:
  python -m app.seed

Creates:
  - Super admin user
  - 6 categories
  - 12+ products with variants and images
  - 3 coupon codes
  - Manual shipping provider
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed():
    from app.models import (
        User, Category, Product, ProductVariant, ProductImage,
        Coupon, ShippingProvider,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # ── Super Admin ───────────────────────────────────────────
        from sqlalchemy import select
        existing = (await session.execute(
            select(User).where(User.email == "admin@zarijasi.com")
        )).scalar_one_or_none()

        if not existing:
            admin = User(
                email="admin@zarijasi.com",
                phone="9999999999",
                first_name="Admin",
                last_name="Zari",
                password_hash=hash_password("Admin@12345"),
                role="super_admin",
                is_verified=True,
                is_active=True,
            )
            session.add(admin)
            logger.info("✅ Super admin created: admin@zarijasi.com / Admin@12345")

        # ── Categories ────────────────────────────────────────────
        categories_data = [
            {"name": "Sarees", "slug": "sarees", "description": "Traditional and contemporary sarees from across India", "image_url": None},
            {"name": "Lehengas", "slug": "lehengas", "description": "Bridal and festive lehengas with intricate craftsmanship", "image_url": None},
            {"name": "Kurtas", "slug": "kurtas", "description": "Elegant kurta sets for everyday and occasion wear", "image_url": None},
            {"name": "Dupattas", "slug": "dupattas", "description": "Handwoven and embroidered dupattas", "image_url": None},
            {"name": "Blouses", "slug": "blouses", "description": "Designer blouses for every saree", "image_url": None},
            {"name": "Accessories", "slug": "accessories", "description": "Jewelry, clutches, and fashion accessories", "image_url": None},
        ]
        cat_map = {}
        for cd in categories_data:
            existing_cat = (await session.execute(
                select(Category).where(Category.slug == cd["slug"])
            )).scalar_one_or_none()
            if not existing_cat:
                cat = Category(**cd)
                session.add(cat)
                await session.flush()
                cat_map[cd["slug"]] = cat.id
                logger.info(f"  📁 Category: {cd['name']}")
            else:
                cat_map[cd["slug"]] = existing_cat.id

        # ── Products ──────────────────────────────────────────────
        products_data = [
            {
                "name": "Banarasi Silk Saree — Royal Purple",
                "slug": "banarasi-silk-saree-royal-purple",
                "description": "A stunning Banarasi silk saree in rich royal purple, featuring intricate gold zari work with traditional motifs. Handwoven by master artisans in Varanasi, this saree is perfect for weddings and festive occasions.\n\nFabric: Pure Banarasi Silk\nWork: Gold Zari Weaving\nOccasion: Wedding, Festival, Reception\nCare: Dry clean only",
                "short_description": "Handwoven Banarasi silk with intricate gold zari motifs",
                "category": "sarees",
                "base_price": 8999, "sale_price": 7499, "is_featured": True,
                "tags": ["banarasi", "silk", "zari", "wedding", "handwoven"],
                "variants": [
                    {"size": "Free Size", "color": "Royal Purple", "color_hex": "#6B2C91", "sku": "BNR-PUR-001", "stock_qty": 12},
                ],
            },
            {
                "name": "Chanderi Cotton Saree — Ocean Blue",
                "slug": "chanderi-cotton-saree-ocean-blue",
                "description": "Lightweight Chanderi cotton saree in a beautiful ocean blue shade with gold border work. Ideal for summer occasions and office wear.\n\nFabric: Chanderi Cotton\nWork: Gold Border\nOccasion: Office, Casual, Festive\nCare: Hand wash in cold water",
                "short_description": "Lightweight Chanderi cotton with elegant gold border",
                "category": "sarees",
                "base_price": 3499, "sale_price": 2999, "is_featured": True,
                "tags": ["chanderi", "cotton", "office", "summer"],
                "variants": [
                    {"size": "Free Size", "color": "Ocean Blue", "color_hex": "#1E6091", "sku": "CHN-BLU-001", "stock_qty": 20},
                ],
            },
            {
                "name": "Bridal Lehenga — Crimson Dream",
                "slug": "bridal-lehenga-crimson-dream",
                "description": "An exquisite bridal lehenga in deep crimson red with heavy handwork embroidery. Features a flared skirt, fitted choli, and matching dupatta adorned with sequins, pearls, and zardozi work.\n\nFabric: Raw Silk & Net\nWork: Zardozi, Sequins, Pearl\nOccasion: Wedding, Engagement\nCare: Dry clean only",
                "short_description": "Heavy handwork bridal lehenga with zardozi embroidery",
                "category": "lehengas",
                "base_price": 24999, "sale_price": 19999, "is_featured": True,
                "tags": ["bridal", "lehenga", "zardozi", "wedding", "handwork"],
                "variants": [
                    {"size": "S", "color": "Crimson", "color_hex": "#9B1B30", "sku": "LHG-CRM-S", "stock_qty": 3},
                    {"size": "M", "color": "Crimson", "color_hex": "#9B1B30", "sku": "LHG-CRM-M", "stock_qty": 5},
                    {"size": "L", "color": "Crimson", "color_hex": "#9B1B30", "sku": "LHG-CRM-L", "stock_qty": 4},
                    {"size": "XL", "color": "Crimson", "color_hex": "#9B1B30", "sku": "LHG-CRM-XL", "stock_qty": 2},
                ],
            },
            {
                "name": "Festive Lehenga — Teal Elegance",
                "slug": "festive-lehenga-teal-elegance",
                "description": "A beautiful festive lehenga in teal green with gold and silver thread work. Perfect for sangeet, mehendi, and festival celebrations.\n\nFabric: Georgette & Net\nWork: Thread Embroidery\nOccasion: Festival, Sangeet, Mehendi\nCare: Dry clean recommended",
                "short_description": "Georgette festive lehenga with dual-tone thread embroidery",
                "category": "lehengas",
                "base_price": 14999, "sale_price": 12999, "is_featured": True,
                "tags": ["lehenga", "festive", "sangeet", "embroidery"],
                "variants": [
                    {"size": "S", "color": "Teal", "color_hex": "#006D6F", "sku": "LHG-TL-S", "stock_qty": 6},
                    {"size": "M", "color": "Teal", "color_hex": "#006D6F", "sku": "LHG-TL-M", "stock_qty": 8},
                    {"size": "L", "color": "Teal", "color_hex": "#006D6F", "sku": "LHG-TL-L", "stock_qty": 5},
                ],
            },
            {
                "name": "Chikankari Kurta Set — Ivory White",
                "slug": "chikankari-kurta-set-ivory-white",
                "description": "Elegant Lucknowi Chikankari kurta set in pristine ivory white. The intricate hand-embroidered patterns make this a versatile piece for both casual and semi-formal occasions.\n\nFabric: Cotton Cambric\nWork: Lucknowi Chikankari\nSet Includes: Kurta + Palazzo + Dupatta\nCare: Hand wash",
                "short_description": "Hand-embroidered Lucknowi Chikankari 3-piece set",
                "category": "kurtas",
                "base_price": 4999, "sale_price": 3999, "is_featured": True,
                "tags": ["chikankari", "kurta", "lucknow", "cotton", "set"],
                "variants": [
                    {"size": "XS", "color": "Ivory", "color_hex": "#FFFFF0", "sku": "KRT-IVR-XS", "stock_qty": 10},
                    {"size": "S", "color": "Ivory", "color_hex": "#FFFFF0", "sku": "KRT-IVR-S", "stock_qty": 15},
                    {"size": "M", "color": "Ivory", "color_hex": "#FFFFF0", "sku": "KRT-IVR-M", "stock_qty": 18},
                    {"size": "L", "color": "Ivory", "color_hex": "#FFFFF0", "sku": "KRT-IVR-L", "stock_qty": 12},
                    {"size": "XL", "color": "Ivory", "color_hex": "#FFFFF0", "sku": "KRT-IVR-XL", "stock_qty": 7},
                ],
            },
            {
                "name": "Silk Anarkali Kurta — Dusty Rose",
                "slug": "silk-anarkali-kurta-dusty-rose",
                "description": "A flowy silk Anarkali kurta in a dreamy dusty rose shade with delicate mirror work. The A-line silhouette flatters every body type.\n\nFabric: Art Silk\nWork: Mirror & Thread\nOccasion: Festive, Party\nCare: Dry clean only",
                "short_description": "Flowy silk Anarkali with delicate mirror work accents",
                "category": "kurtas",
                "base_price": 5999, "sale_price": None, "is_featured": True,
                "tags": ["anarkali", "silk", "mirror-work", "party"],
                "variants": [
                    {"size": "S", "color": "Dusty Rose", "color_hex": "#D4A0A7", "sku": "ANK-RSE-S", "stock_qty": 8},
                    {"size": "M", "color": "Dusty Rose", "color_hex": "#D4A0A7", "sku": "ANK-RSE-M", "stock_qty": 10},
                    {"size": "L", "color": "Dusty Rose", "color_hex": "#D4A0A7", "sku": "ANK-RSE-L", "stock_qty": 6},
                ],
            },
            {
                "name": "Phulkari Dupatta — Sunset Orange",
                "slug": "phulkari-dupatta-sunset-orange",
                "description": "Vibrant Phulkari dupatta hand-embroidered by artisans from Punjab. Features traditional floral patterns in sunset orange and gold threads.\n\nFabric: Chiffon\nWork: Phulkari Hand Embroidery\nSize: 2.5 meters\nCare: Hand wash",
                "short_description": "Hand-embroidered Phulkari dupatta from Punjab artisans",
                "category": "dupattas",
                "base_price": 2499, "sale_price": 1999, "is_featured": False,
                "tags": ["phulkari", "dupatta", "punjabi", "embroidery"],
                "variants": [
                    {"size": "Free Size", "color": "Sunset Orange", "color_hex": "#E8702A", "sku": "DPT-ORG-001", "stock_qty": 25},
                ],
            },
            {
                "name": "Embroidered Blouse — Midnight Black",
                "slug": "embroidered-blouse-midnight-black",
                "description": "Intricately embroidered designer blouse in midnight black. Features gold threadwork on premium raw silk, designed to pair with any saree.\n\nFabric: Raw Silk\nWork: Gold Thread Embroidery\nClosure: Back hooks\nCare: Dry clean only",
                "short_description": "Designer raw silk blouse with gold threadwork",
                "category": "blouses",
                "base_price": 2999, "sale_price": 2499, "is_featured": False,
                "tags": ["blouse", "designer", "silk", "embroidery"],
                "variants": [
                    {"size": "32", "color": "Black", "color_hex": "#1A1A2E", "sku": "BLS-BLK-32", "stock_qty": 10},
                    {"size": "34", "color": "Black", "color_hex": "#1A1A2E", "sku": "BLS-BLK-34", "stock_qty": 12},
                    {"size": "36", "color": "Black", "color_hex": "#1A1A2E", "sku": "BLS-BLK-36", "stock_qty": 15},
                    {"size": "38", "color": "Black", "color_hex": "#1A1A2E", "sku": "BLS-BLK-38", "stock_qty": 8},
                    {"size": "40", "color": "Black", "color_hex": "#1A1A2E", "sku": "BLS-BLK-40", "stock_qty": 5},
                ],
            },
        ]

        for pd in products_data:
            existing_prod = (await session.execute(
                select(Product).where(Product.slug == pd["slug"])
            )).scalar_one_or_none()
            if existing_prod:
                continue

            product = Product(
                name=pd["name"],
                slug=pd["slug"],
                description=pd["description"],
                short_description=pd["short_description"],
                category_id=cat_map.get(pd["category"]),
                base_price=pd["base_price"],
                sale_price=pd.get("sale_price"),
                is_active=True,
                is_featured=pd.get("is_featured", False),
                meta_title=pd["name"][:60],
                tags=pd.get("tags"),
            )
            session.add(product)
            await session.flush()

            for vd in pd.get("variants", []):
                variant = ProductVariant(product_id=product.id, **vd, is_active=True)
                session.add(variant)

            logger.info(f"  🛍️ Product: {pd['name']} ({len(pd.get('variants', []))} variants)")

        # ── Coupons ───────────────────────────────────────────────
        coupons_data = [
            {"code": "WELCOME10", "type": "percent", "value": 10, "max_discount": 500, "min_order_amount": 999, "usage_limit": 100},
            {"code": "FLAT200", "type": "flat", "value": 200, "min_order_amount": 2000, "usage_limit": 50},
            {"code": "BRIDAL15", "type": "percent", "value": 15, "max_discount": 3000, "min_order_amount": 10000, "usage_limit": 20},
        ]
        for cd in coupons_data:
            existing_cpn = (await session.execute(
                select(Coupon).where(Coupon.code == cd["code"])
            )).scalar_one_or_none()
            if not existing_cpn:
                coupon = Coupon(
                    **cd,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=365),
                    is_active=True,
                )
                session.add(coupon)
                logger.info(f"  🎟️ Coupon: {cd['code']}")

        # ── Shipping Provider ─────────────────────────────────────
        existing_sp = (await session.execute(
            select(ShippingProvider).where(ShippingProvider.slug == "manual")
        )).scalar_one_or_none()
        if not existing_sp:
            sp = ShippingProvider(
                name="Manual (Admin Managed)",
                slug="manual",
                description="Admin manually enters tracking info and manages shipments",
                is_active=True,
                is_configured=True,
                config={},
            )
            session.add(sp)
            logger.info("  🚚 Shipping: Manual provider")

        await session.commit()
        logger.info("\n🎉 Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
