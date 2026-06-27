"""
Comprehensive API test suite for Zari & Jasi backend.
Run: python api_tests.py
"""
import asyncio
import json
import httpx

BASE = "http://localhost:8000/api/v1"
RESULTS = []

def log(test, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    RESULTS.append({"test": test, "passed": passed, "detail": detail})
    print(f"{status} | {test}" + (f"\n       ↳ {detail}" if detail and not passed else ""))

async def run_tests():
    async with httpx.AsyncClient(timeout=30) as c:
        # ── HEALTH ──────────────────────────────────────────────────────────────
        r = await c.get("http://localhost:8000/health")
        log("Health check", r.status_code == 200, r.text)

        # ── CATEGORIES ──────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/categories")
        cats = r.json() if r.status_code == 200 else []
        log("GET /categories", r.status_code == 200 and len(cats) > 0, f"Count: {len(cats)}, status: {r.status_code}")
        cat_id = cats[0]["id"] if cats else None

        # ── PRODUCTS ────────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/products")
        prods_data = r.json() if r.status_code == 200 else {}
        log("GET /products", r.status_code == 200, f"Status: {r.status_code}, keys: {list(prods_data.keys()) if isinstance(prods_data, dict) else 'list'}")

        r = await c.get(f"{BASE}/products/featured?limit=4")
        feat = r.json() if r.status_code == 200 else []
        log("GET /products/featured", r.status_code == 200 and len(feat) > 0, f"Count: {len(feat)}")
        test_slug = feat[0]["slug"] if feat else None

        if test_slug:
            r = await c.get(f"{BASE}/products/{test_slug}")
            log("GET /products/:slug", r.status_code == 200, f"Slug: {test_slug}")

        if cat_id:
            r = await c.get(f"{BASE}/categories/{cats[0]['slug']}/products")
            log("GET /categories/:slug/products", r.status_code == 200, f"Status: {r.status_code}")

        # ── AUTH — REGISTER ──────────────────────────────────────────────────────
        reg_payload = {
            "email": "testuser@zarijasi.com",
            "password": "Test@1234",
            "first_name": "Test",
            "last_name": "User",
            "phone": "9876543210"
        }
        r = await c.post(f"{BASE}/auth/register", json=reg_payload)
        reg_data = r.json()
        log("POST /auth/register", r.status_code == 200 and "access_token" in reg_data, f"Status: {r.status_code}, keys: {list(reg_data.keys())}")
        user_token = reg_data.get("access_token", "")

        # ── AUTH — LOGIN ─────────────────────────────────────────────────────────
        r = await c.post(f"{BASE}/auth/login", json={"email": "testuser@zarijasi.com", "password": "Test@1234"})
        login_data = r.json()
        log("POST /auth/login", r.status_code == 200 and "access_token" in login_data, f"Status: {r.status_code}")
        if "access_token" in login_data:
            user_token = login_data["access_token"]

        # ── AUTH — REFRESH ────────────────────────────────────────────────────────
        r2_token = login_data.get("refresh_token", "")
        if r2_token:
            r = await c.post(f"{BASE}/auth/refresh", json={"refresh_token": r2_token})
            log("POST /auth/refresh", r.status_code == 200 and "access_token" in r.json(), f"Status: {r.status_code}")

        # ── AUTH — ME ─────────────────────────────────────────────────────────────
        headers = {"Authorization": f"Bearer {user_token}"}
        r = await c.get(f"{BASE}/auth/me", headers=headers)
        me_data = r.json()
        log("GET /auth/me", r.status_code == 200 and "email" in me_data, f"Status: {r.status_code}")

        # ── ADMIN LOGIN ───────────────────────────────────────────────────────────
        r = await c.post(f"{BASE}/auth/login", json={"email": "admin@zarijasi.com", "password": "Admin@12345"})
        admin_data = r.json()
        log("Admin login", r.status_code == 200 and admin_data.get("user", {}).get("role") in ("admin", "super_admin"), f"Status: {r.status_code}, role: {admin_data.get('user', {}).get('role')}")
        admin_token = admin_data.get("access_token", "")
        admin_h = {"Authorization": f"Bearer {admin_token}"}

        # ── CART ──────────────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/customer/cart", headers=headers)
        log("GET /customer/cart", r.status_code == 200, f"Status: {r.status_code}")

        # Get a variant to add to cart
        if feat:
            prod_r = await c.get(f"{BASE}/products/{feat[0]['slug']}")
            if prod_r.status_code == 200:
                prod = prod_r.json()
                variants = prod.get("variants", [])
                if variants:
                    variant_id = variants[0]["id"]
                    r = await c.post(f"{BASE}/customer/cart", json={"variant_id": variant_id, "quantity": 1}, headers=headers)
                    log("POST /customer/cart (add item)", r.status_code == 200, f"Status: {r.status_code}, resp: {r.text[:100]}")
                    cart_r = await c.get(f"{BASE}/customer/cart", headers=headers)
                    cart_data = cart_r.json()
                    log("GET /customer/cart (has items)", cart_r.status_code == 200 and len(cart_data.get("items", [])) > 0, f"Item count: {len(cart_data.get('items', []))}")

                    if cart_data.get("items"):
                        item_id = cart_data["items"][0]["id"]
                        r = await c.put(f"{BASE}/customer/cart/{item_id}", json={"quantity": 2}, headers=headers)
                        log("PUT /customer/cart/:id (update qty)", r.status_code == 200, f"Status: {r.status_code}")

        # ── COUPON APPLY ──────────────────────────────────────────────────────────
        r = await c.post(f"{BASE}/customer/cart/apply-coupon", json={"code": "WELCOME10"}, headers=headers)
        log("POST /customer/cart/apply-coupon", r.status_code in (200, 400), f"Status: {r.status_code}, resp: {r.text[:80]}")

        # ── WISHLIST ──────────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/customer/wishlist", headers=headers)
        log("GET /customer/wishlist", r.status_code == 200, f"Status: {r.status_code}")
        if feat:
            prod_id = feat[0]["id"]
            r = await c.post(f"{BASE}/customer/wishlist/{prod_id}", headers=headers)
            log("POST /customer/wishlist/:id (add)", r.status_code == 200, f"Status: {r.status_code}")
            r = await c.get(f"{BASE}/customer/wishlist", headers=headers)
            log("GET /customer/wishlist (has items)", r.status_code == 200 and len(r.json().get("items", [])) > 0, f"Count: {len(r.json().get('items', []))}")
            r = await c.delete(f"{BASE}/customer/wishlist/{prod_id}", headers=headers)
            log("DELETE /customer/wishlist/:id", r.status_code == 200, f"Status: {r.status_code}")

        # ── CUSTOMER PROFILE ──────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/customer/profile", headers=headers)
        log("GET /customer/profile", r.status_code == 200, f"Status: {r.status_code}")

        # ── CUSTOMER ADDRESSES ────────────────────────────────────────────────────
        addr_payload = {
            "name": "Test User", "phone": "9876543210",
            "line1": "123 Test Street", "city": "Mumbai",
            "state": "Maharashtra", "pincode": "400001", "country": "India",
            "is_default": True
        }
        r = await c.post(f"{BASE}/customer/addresses", json=addr_payload, headers=headers)
        addr_data = r.json()
        log("POST /customer/addresses", r.status_code == 200 and "id" in addr_data, f"Status: {r.status_code}")
        addr_id = addr_data.get("id", "")

        r = await c.get(f"{BASE}/customer/addresses", headers=headers)
        log("GET /customer/addresses", r.status_code == 200, f"Status: {r.status_code}, count: {len(r.json())}")

        # ── ADMIN DASHBOARD ───────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/dashboard/stats", headers=admin_h)
        log("GET /admin/dashboard/stats", r.status_code == 200, f"Status: {r.status_code}")

        r = await c.get(f"{BASE}/admin/dashboard/revenue-chart", headers=admin_h)
        log("GET /admin/dashboard/revenue-chart", r.status_code == 200, f"Status: {r.status_code}")

        r = await c.get(f"{BASE}/admin/dashboard/top-products", headers=admin_h)
        log("GET /admin/dashboard/top-products", r.status_code == 200, f"Status: {r.status_code}")

        # ── ADMIN PRODUCTS ────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/products", headers=admin_h)
        log("GET /admin/products", r.status_code == 200, f"Status: {r.status_code}")

        admin_prods = r.json() if r.status_code == 200 else {}
        prods_list = admin_prods.get("data", []) if isinstance(admin_prods, dict) else admin_prods
        first_pid = prods_list[0]["id"] if prods_list else None

        if first_pid:
            r = await c.get(f"{BASE}/admin/products/{first_pid}", headers=admin_h)
            log("GET /admin/products/:id", r.status_code == 200, f"Status: {r.status_code}")
            r = await c.post(f"{BASE}/admin/products/{first_pid}/images/upload-url", headers=admin_h, params={"filename": "test.jpg"})
            log("POST /admin/products/:id/images/upload-url", r.status_code == 200, f"Status: {r.status_code}, resp: {r.text[:80]}")

        # ── ADMIN CATEGORIES ──────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/categories", headers=admin_h)
        log("GET /admin/categories", r.status_code == 200, f"Status: {r.status_code}")

        # ── ADMIN COUPONS ──────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/coupons", headers=admin_h)
        log("GET /admin/coupons", r.status_code == 200, f"Status: {r.status_code}, count: {len(r.json()) if r.status_code==200 else 'err'}")

        # ── ADMIN CUSTOMERS ───────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/customers", headers=admin_h)
        log("GET /admin/customers", r.status_code == 200, f"Status: {r.status_code}")

        # ── ADMIN INVENTORY ───────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/inventory", headers=admin_h)
        log("GET /admin/inventory", r.status_code == 200, f"Status: {r.status_code}")

        # ── ADMIN ORDERS ──────────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/orders", headers=admin_h)
        log("GET /admin/orders", r.status_code == 200, f"Status: {r.status_code}")

        # ── SHIPPING PROVIDERS ────────────────────────────────────────────────────
        r = await c.get(f"{BASE}/admin/shipping/providers", headers=admin_h)
        log("GET /admin/shipping/providers", r.status_code == 200, f"Status: {r.status_code}")

        # ── ORDERS — COD FLOW ─────────────────────────────────────────────────────
        if addr_id:
            # Ensure cart has items first
            cart_check = await c.get(f"{BASE}/customer/cart", headers=headers)
            cart_items = cart_check.json().get("items", [])
            if not cart_items and feat:
                prod_r = await c.get(f"{BASE}/products/{feat[0]['slug']}")
                if prod_r.status_code == 200:
                    variants = prod_r.json().get("variants", [])
                    if variants:
                        await c.post(f"{BASE}/customer/cart", json={"variant_id": variants[0]["id"], "quantity": 1}, headers=headers)

            r = await c.post(f"{BASE}/orders", json={
                "address_id": addr_id,
                "payment_method": "cod",
                "coupon_code": "WELCOME10"
            }, headers=headers)
            order_data = r.json()
            log("POST /orders (COD + coupon)", r.status_code == 200 and "id" in order_data, f"Status: {r.status_code}, resp: {str(order_data)[:120]}")
            order_id = order_data.get("id", "")

            if order_id:
                # Get order
                r = await c.get(f"{BASE}/orders/{order_id}", headers=headers)
                log("GET /orders/:id", r.status_code == 200, f"Status: {r.status_code}")

                # List orders
                r = await c.get(f"{BASE}/orders", headers=headers)
                log("GET /orders (list)", r.status_code == 200, f"Status: {r.status_code}")

                # Generate invoice (admin)
                r = await c.post(f"{BASE}/admin/orders/{order_id}/generate-invoice", headers=admin_h)
                log("POST /admin/orders/:id/generate-invoice", r.status_code == 200, f"Status: {r.status_code}, resp: {r.text[:100]}")

                # Download invoice
                r = await c.get(f"{BASE}/invoices/{order_id}/download", headers=headers)
                log("GET /invoices/:id/download", r.status_code == 200, f"Status: {r.status_code}")

        # ── RAZORPAY ORDER CREATION ────────────────────────────────────────────────
        # Re-add to cart and create razorpay order
        if feat:
            prod_r = await c.get(f"{BASE}/products/{feat[0]['slug']}")
            if prod_r.status_code == 200:
                variants = prod_r.json().get("variants", [])
                if variants and addr_id:
                    await c.post(f"{BASE}/customer/cart", json={"variant_id": variants[0]["id"], "quantity": 1}, headers=headers)
                    r = await c.post(f"{BASE}/orders", json={"address_id": addr_id, "payment_method": "razorpay"}, headers=headers)
                    rp_order = r.json()
                    rp_order_id = rp_order.get("id", "")
                    log("POST /orders (Razorpay)", r.status_code == 200, f"Status: {r.status_code}")
                    if rp_order_id:
                        r = await c.post(f"{BASE}/payments/create-razorpay-order", headers=headers, params={"order_id": rp_order_id})
                        log("POST /payments/create-razorpay-order", r.status_code == 200, f"Status: {r.status_code}, resp: {r.text[:120]}")

    # ── SUMMARY ───────────────────────────────────────────────────────────────────
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")
    if failed:
        print("\nFAILED TESTS:")
        for r in RESULTS:
            if not r["passed"]:
                print(f"  ❌ {r['test']}: {r['detail']}")

asyncio.run(run_tests())
