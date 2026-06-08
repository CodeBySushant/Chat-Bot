"""Aggregate v1 routers."""
from fastapi import APIRouter

from app.api.v1 import auth, chatbots, companies, crawls, documents, users
from app.api.v1 import chat, widget, leads, analytics, billing, admin

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(companies.router)
api_router.include_router(chatbots.router)
api_router.include_router(documents.router)
api_router.include_router(crawls.router)
api_router.include_router(chat.router)
api_router.include_router(widget.router)
api_router.include_router(leads.router)
api_router.include_router(analytics.router)
api_router.include_router(billing.router)
api_router.include_router(admin.router)
