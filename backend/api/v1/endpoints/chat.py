"""Chat endpoints for AI conversations about posts."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """
    Get chat history for a post.

    Returns all chat messages associated with a specific post,
    ordered chronologically.
    """
    try:
        logger.info("Getting chat history", post_id=post_id)

        messages = await chat_service.get_chat_history(post_id, db)

        return ChatHistoryResponse(
            post_id=post_id,
            messages=messages,
            total_messages=len(messages),
        )

    except ValueError as e:
        logger.warning("Post not found for chat history", post_id=post_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Error getting chat history", post_id=post_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get chat history: {str(e)}")


@router.get("/suggestions/{post_id}")
async def get_suggested_questions(
    post_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[str]:
    """
    Get suggested questions for a post.

    Returns contextual question suggestions based on the post's
    analysis and existing chat history.
    """
    try:
        # This is a simplified version - you could enhance this
        # to be more context-aware
        from models import Post
        from sqlalchemy import select

        result = await db.execute(select(Post).where(Post.post_id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Post with ID {post_id} not found")

        questions = [
            "What specific patterns indicate this is AI-generated?",
            "How confident are you in this analysis?",
            "Could this be a false positive?",
        ]

        if post.verdict == "ai_slop":
            questions.append("What makes this different from human writing?")
        else:
            questions.append("Why do you think this is human-written?")

        return questions[:3]

    except ValueError as e:
        logger.warning("Post not found for suggestions", post_id=post_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Error getting suggestions", post_id=post_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get suggestions: {str(e)}")
