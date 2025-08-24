"""Chat endpoints for AI conversations about posts."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.chat import ChatRequest, ChatResponse, Message
from services.chat_service import ChatService
from utils.logging import get_logger


class ChatHistoryResponse(BaseModel):
    """Response for chat history."""

    post_id: str = Field(..., description="Facebook post ID")
    messages: List[Message] = Field(default_factory=list, description="Chat messages")
    total_messages: int = Field(..., description="Total number of messages")


logger = get_logger(__name__)

router = APIRouter(tags=["chat"])

# Initialize service
chat_service = ChatService()


@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Send a message about a post and get AI response with multimodal support.

    This endpoint allows users to ask questions about a post's AI detection
    analysis and receive AI-generated responses with context. Supports image
    analysis for comprehensive multimodal AI detection insights.
    """
    try:
        logger.info(
            "Sending chat message",
            post_id=request.post_id,
            user_id=request.user_id,
            message_length=len(request.message),
        )

        response = await chat_service.send_message(request, db)

        logger.info(
            "Chat response generated",
            post_id=request.post_id,
            user_id=request.user_id,
            response_length=len(response.message),
            has_images=response.context.get("has_images", False),
        )

        return response

    except ValueError as e:
        logger.warning("Post not found for chat", post_id=request.post_id, user_id=request.user_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Error sending chat message", post_id=request.post_id, user_id=request.user_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate response: {str(e)}")


@router.get("/history/{post_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    post_id: str,
    user_id: str = Query(..., description="User identifier to get user-specific chat history"),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """
    Get user-specific chat history for a post.

    Returns chat messages from the specific user's conversation with the AI
    about this post, ordered chronologically. Each user has their own
    isolated chat history per post.
    """
    try:
        logger.info("Getting user-specific chat history", post_id=post_id, user_id=user_id)

        messages = await chat_service.get_user_chat_history(post_id, user_id, db)

        return ChatHistoryResponse(
            post_id=post_id,
            messages=messages,
            total_messages=len(messages),
        )

    except ValueError as e:
        logger.warning("Post not found for chat history", post_id=post_id, user_id=user_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Error getting chat history", post_id=post_id, user_id=user_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get chat history: {str(e)}")
