"""Abstract billing provider interface (Stripe / LemonSqueezy / Paddle)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CheckoutSession:
    url: str
    provider_ref: str


@dataclass
class ProviderSubscription:
    provider_subscription_id: str
    status: str
    raw: dict = field(default_factory=dict)


class BillingProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def create_checkout(self, *, company_id: str, plan_code: str, success_url: str, cancel_url: str) -> CheckoutSession:
        ...

    @abstractmethod
    async def create_subscription(self, *, company_id: str, plan_code: str) -> ProviderSubscription:
        ...

    @abstractmethod
    async def cancel_subscription(self, *, provider_subscription_id: str, at_period_end: bool = True) -> ProviderSubscription:
        ...

    @abstractmethod
    async def parse_webhook(self, *, payload: bytes, signature: str | None) -> dict:
        ...
