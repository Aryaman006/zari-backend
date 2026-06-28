import unittest
from typing import Optional
from app.services.storage_service import SupabaseStorageService
from app.core.config import settings

class TestSupabaseStorageBucketRouting(unittest.TestCase):
    def setUp(self):
        # Temporarily mock SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to avoid validation error during init
        self.original_url = settings.SUPABASE_URL
        self.original_key = settings.SUPABASE_SERVICE_ROLE_KEY
        settings.SUPABASE_URL = "https://mockproject.supabase.co"
        settings.SUPABASE_SERVICE_ROLE_KEY = "mockkey"
        self.storage = SupabaseStorageService()

    def tearDown(self):
        settings.SUPABASE_URL = self.original_url
        settings.SUPABASE_SERVICE_ROLE_KEY = self.original_key

    def test_public_buckets_routing(self):
        # Product images folder prefix
        self.assertEqual(self.storage._get_bucket("products/123/img.jpg"), "product-images")
        self.assertEqual(self.storage._get_bucket("product/img.jpg"), "product-images")

        # Category images
        self.assertEqual(self.storage._get_bucket("categories/cat.png"), "category-images")
        self.assertEqual(self.storage._get_bucket("category/icon.png"), "category-images")

        # Brand images
        self.assertEqual(self.storage._get_bucket("brands/brand.png"), "brand-images")
        self.assertEqual(self.storage._get_bucket("brand/logo.png"), "brand-images")

        # Banners
        self.assertEqual(self.storage._get_bucket("banners/slide1.jpg"), "banners")
        self.assertEqual(self.storage._get_bucket("banner/hero.jpg"), "banners")

    def test_private_buckets_routing(self):
        # Invoices
        self.assertEqual(self.storage._get_bucket("invoices/2026/06/invoice.pdf"), "invoices")
        self.assertEqual(self.storage._get_bucket("invoice/pdf.pdf"), "invoices")

        # User uploads
        self.assertEqual(self.storage._get_bucket("avatars/user1.jpg"), "user-uploads")
        self.assertEqual(self.storage._get_bucket("user-uploads/doc.pdf"), "user-uploads")

    def test_explicit_bucket_override(self):
        # If bucket is explicitly supplied, routing is bypassed
        self.assertEqual(self.storage._get_bucket("products/123/img.jpg", bucket="custom-bucket"), "custom-bucket")
        self.assertEqual(self.storage._get_bucket("invoices/inv.pdf", bucket="my-private-invoices"), "my-private-invoices")

    def test_unresolved_bucket_raises_error(self):
        # Unknown folders must raise ValueError to prevent defaulting to single bucket
        with self.assertRaises(ValueError):
            self.storage._get_bucket("unknown_folder/file.txt")
        with self.assertRaises(ValueError):
            self.storage._get_bucket("temp_uploads/doc.pdf")

if __name__ == "__main__":
    unittest.main()
