"""Stripe provider. Production: replace bodies with stripe SDK calls + webhook
signature verification. Shape matches the abstract interface exactly."""
from __future__ import annotations

import uuid

from app.services.billing.providers.base import (
    BillingProvider, CheckoutSession, ProviderSubscription,
)


class StripeProvider(BillingProvider):
    name = "stripe"

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None):
        self._api_key = api_key
        self._webhook_secret = webhook_secret

    async def create_checkout(self, *, company_id, plan_code, success_url, cancel_url) -> CheckoutSession:
        ref = f"cs_test_{uuid.uuid4().hex[:24]}"
        return CheckoutSession(url=f"https://checkout.stripe.com/c/pay/{ref}", provider_ref=ref)

    async def create_subscription(self, *, company_id, plan_code) -> ProviderSubscription:
        return ProviderSubscription(provider_subscription_id=f"sub_{uuid.uuid4().hex[:24]}", status="active")

    async def cancel_subscription(self, *, provider_subscription_id, at_period_end=True) -> ProviderSubscription:
        return ProviderSubscription(
            provider_subscription_id=provider_subscription_id,
            status="canceled" if not at_period_end else "active",
            raw={"cancel_at_period_end": at_period_end},
        )

    async def parse_webhook(self, *, payload, signature) -> dict:
        # Production: stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
        import json
        return json.loads(payload or b"{}")
