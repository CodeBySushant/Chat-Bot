from __future__ import annotations
import uuid
from app.services.billing.providers.base import BillingProvider, CheckoutSession, ProviderSubscription


class PaddleProvider(BillingProvider):
    name = "paddle"

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None):
        self._api_key = api_key
        self._webhook_secret = webhook_secret

    async def create_checkout(self, *, company_id, plan_code, success_url, cancel_url) -> CheckoutSession:
        ref = uuid.uuid4().hex[:24]
        return CheckoutSession(url=f"https://checkout.paddle.com/{ref}", provider_ref=ref)

    async def create_subscription(self, *, company_id, plan_code) -> ProviderSubscription:
        return ProviderSubscription(provider_subscription_id=f"pdl_{uuid.uuid4().hex[:20]}", status="active")

    async def cancel_subscription(self, *, provider_subscription_id, at_period_end=True) -> ProviderSubscription:
        return ProviderSubscription(provider_subscription_id=provider_subscription_id, status="canceled")

    async def parse_webhook(self, *, payload, signature) -> dict:
        import json
        return json.loads(payload or b"{}")
