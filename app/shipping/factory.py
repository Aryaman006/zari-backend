"""
Shipping Provider Factory — resolves slug to provider instance.

To add a new provider:
1. Create provider class in this package
2. Import it below
3. Add to PROVIDER_REGISTRY
4. Seed the provider into shipping_providers table via admin or seed script
"""
from typing import Optional
from app.shipping.base import ShippingProvider
from app.shipping.manual import ManualProvider
from app.shipping.shiprocket import ShiprocketProvider
from app.shipping.delhivery import DelhiveryProvider

# ── Provider Registry ─────────────────────────────────────────────────────────
# Maps slug → provider class
# Add new providers here without any other code changes

PROVIDER_REGISTRY: dict[str, type[ShippingProvider]] = {
    "manual": ManualProvider,
    "shiprocket": ShiprocketProvider,
    "delhivery": DelhiveryProvider,
    # "ekart": EkartProvider,         # Uncomment when implemented
}


def get_provider(slug: str) -> Optional[ShippingProvider]:
    """
    Resolve a provider slug to an instantiated ShippingProvider.
    Returns None if the slug is not registered.
    """
    provider_class = PROVIDER_REGISTRY.get(slug)
    if provider_class is None:
        return None
    return provider_class()


def list_available_providers() -> list[str]:
    """Return all registered provider slugs."""
    return list(PROVIDER_REGISTRY.keys())
