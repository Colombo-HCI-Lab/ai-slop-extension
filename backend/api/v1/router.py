"""
API v1 router configuration.
"""

from fastapi import APIRouter

from api.v1.endpoints import video_detection, health, image_detection, chat, posts

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(image_detection.router, tags=["image-detection"])
api_router.include_router(video_detection.router, tags=["video-detection"])

# New migrated endpoints
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
