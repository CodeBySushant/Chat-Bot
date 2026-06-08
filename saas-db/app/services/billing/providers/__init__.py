"""Billing provider registry + factory (env-driven, like the AI provider layer)."""
from __future__ import annotations

from app.core.config import settings
from app.services.billing.providers.base import BillingProvider
from app.services.billing.providers.lemonsqueezy import LemonSqueezyProvider
from app.services.billing.providers.paddle import PaddleProvider
from app.services.billing.providers.stripe import StripeProvider

_REGISTRY = {
    "stripe": lambda: StripeProvider(
        getattr(settings, "STRIPE_API_KEY", None), getattr(settings, "STRIPE_WEBHOOK_SECRET", None)),
    "lemonsqueezy": lambda: LemonSqueezyProvider(getattr(settings, "LEMONSQUEEZY_API_KEY", None)),
    "paddle": lambda: PaddleProvider(getattr(settings, "PADDLE_API_KEY", None)),
}
_instances: dict[str, BillingProvider] = {}


def get_billing_provider(name: str | None = None) -> BillingProvider:
    name = (name or getattr(settings, "BILLING_PROVIDER", "stripe")).lower()
    if name not in _REGISTRY:
        from app.core.exceptions import ValidationFailed
        raise ValidationFailed(f"Unknown billing provider '{name}'")
    if name not in _instances:
        _instances[name] = _REGISTRY[name]()
    return _instances[name]


__all__ = ["BillingProvider", "get_billing_provider"]
