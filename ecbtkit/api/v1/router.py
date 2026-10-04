"""Aggregate v1 API router."""

from fastapi import APIRouter

from ecbtkit.api.v1 import auth, questions, exams, attempts, health

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(questions.router)
api_router.include_router(exams.router)
api_router.include_router(attempts.router)
