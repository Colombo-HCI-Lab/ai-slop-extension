"""Chat endpoints for AI conversations about posts."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.chat_service import ChatService


class ChatRequest(BaseModel):
    """Request for sending a chat message."""

    post_id: str = Field(..., description="Facebook post ID")
    message: str = Field(..., description="User message")


class Message(BaseModel):
    """Chat message."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    message: str = Field(..., description="Message content")
    created_at: str = Field(..., description="Message timestamp")


class ChatResponse(BaseModel):
    """Response for chat message."""

    id: str = Field(..., description="Response message ID")
    message: str = Field(..., description="AI response message")
    suggested_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context about the response")
    timestamp: str = Field(..., description="Response timestamp")


class ChatHistoryResponse(BaseModel):
    """Response for chat history."""

    post_id: str = Field(..., description="Facebook post ID")
    messages: List[Message] = Field(default_factory=list, description="Chat messages")
    total_messages: int = Field(..., description="Total number of messages")


logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Initialize service
chat_service = ChatService()


@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Send a message about a post and get AI response.

    This endpoint allows users to ask questions about a post's AI detection
    analysis and receive AI-generated responses with context.
    """
    try:
        logger.info(f"Sending chat message for post {request.post_id}")

        response = await chat_service.send_message(request, db)

        logger.info(f"Chat response generated for post {request.post_id}")

        return response

    except ValueError as e:
        logger.warning(f"Post not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending chat message: {e}")
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
        logger.info(f"Getting chat history for post {post_id}")

        messages = await chat_service.get_chat_history(post_id, db)

        return ChatHistoryResponse(
            post_id=post_id,
            messages=messages,
            total_messages=len(messages),
        )

    except ValueError as e:
        logger.warning(f"Post not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
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
        logger.warning(f"Post not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get suggestions: {str(e)}")
