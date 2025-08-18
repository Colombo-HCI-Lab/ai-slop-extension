"""Chat service for Google Gemini integration."""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from models import Chat, Post
from schemas.chat import ChatRequest, ChatResponse, Message

logger = logging.getLogger(__name__)

# Configure Gemini API
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)


class ChatService:
    """Service for managing chat conversations about posts using Google Gemini."""

    def __init__(self):
        """Initialize the chat service."""
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not configured - chat service will use mock responses")

        self.model = genai.GenerativeModel("gemini-pro") if settings.gemini_api_key else None

    async def send_message(
        self,
        request: ChatRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        """
        Send a message about a post and get AI response.

        Args:
            request: Chat request with post ID and message
            db: Database session

        Returns:
            Chat response with AI-generated reply
        """
        # Get post from database
        post = await self._get_post(request.post_id, db)
        if not post:
            raise ValueError(f"Post with ID {request.post_id} not found")

        # Save user message
        user_chat = await self._save_message(post.id, "user", request.message, db)

        # Get chat history for context
        chat_history = await self._get_chat_history(post.id, db)

        # Generate AI response
        response_text = await self._generate_response(post, request.message, chat_history)

        # Save AI response
        assistant_chat = await self._save_message(post.id, "assistant", response_text, db)

        # Generate suggested questions
        suggested_questions = self._generate_suggested_questions(post, chat_history)

        return ChatResponse(
            id=assistant_chat.id,
            message=response_text,
            suggested_questions=suggested_questions,
            context={
                "sources": ["Content analysis", "Pattern recognition", "Language modeling"],
                "confidence": post.confidence,
                "additional_info": "This analysis is based on multiple AI detection patterns",
            },
            timestamp=assistant_chat.created_at.isoformat(),
        )

    async def get_chat_history(
        self,
        post_id: str,
        db: AsyncSession,
    ) -> List[Message]:
        """
        Get chat history for a post.

        Args:
            post_id: Facebook post ID
            db: Database session

        Returns:
            List of chat messages
        """
        # Get post from database
        post = await self._get_post(post_id, db)
        if not post:
            raise ValueError(f"Post with ID {post_id} not found")

        # Get chat history
        chats = await self._get_chat_history(post.id, db)

        return [
            Message(
                id=chat.id,
                role=chat.role,
                message=chat.message,
                created_at=chat.created_at.isoformat(),
            )
            for chat in chats
        ]

    async def _get_post(self, post_id: str, db: AsyncSession) -> Optional[Post]:
        """Get post by Facebook post ID."""
        result = await db.execute(select(Post).where(Post.post_id == post_id).options(selectinload(Post.chats)))
        return result.scalar_one_or_none()

    async def _get_chat_history(self, post_db_id: str, db: AsyncSession, limit: int = 20) -> List[Chat]:
        """Get chat history for a post."""
        result = await db.execute(select(Chat).where(Chat.post_db_id == post_db_id).order_by(Chat.created_at.asc()).limit(limit))
        return result.scalars().all()

    async def _save_message(
        self,
        post_db_id: str,
        role: str,
        message: str,
        db: AsyncSession,
    ) -> Chat:
        """Save a chat message to database."""
        chat = Chat(
            id=str(uuid.uuid4()),
            post_db_id=post_db_id,
            role=role,
            message=message,
        )

        db.add(chat)
        await db.commit()
        await db.refresh(chat)

        return chat

    async def _generate_response(
        self,
        post: Post,
        user_message: str,
        chat_history: List[Chat],
    ) -> str:
        """Generate AI response using Gemini."""
        if not self.model:
            return self._generate_mock_response(post, user_message)

        # Build context prompt
        system_prompt = f"""You are an AI content detection assistant. You help users understand AI content detection results and answer questions about specific posts.

Post Analysis Context:
- Content: "{post.content[:500]}..."
- Verdict: {post.verdict}
- Confidence: {(post.confidence * 100):.1f}%
- Explanation: {post.explanation}
- Author: {post.author or "Unknown"}

Guidelines:
- Be helpful and informative about AI content detection
- Explain the reasoning behind the analysis
- Be honest about limitations and potential false positives
- Keep responses concise but informative
- Reference the specific post content when relevant"""

        # Build conversation history
        conversation_history = "\n".join(
            f"{chat.role}: {chat.message}"
            for chat in chat_history[:-1]  # Exclude the message we just saved
        )

        full_prompt = f"""{system_prompt}

Previous conversation:
{conversation_history}

User question: {user_message}

Please provide a helpful response about the AI detection analysis."""

        try:
            # Generate response with Gemini
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            return self._generate_mock_response(post, user_message)

    def _generate_mock_response(self, post: Post, user_message: str) -> str:
        """Generate mock response for testing or when Gemini is unavailable."""
        message_lower = user_message.lower()

        if "why" in message_lower:
            if post.verdict == "ai_slop":
                return f"This post was identified as AI-generated content because: {post.explanation}. The content shows typical AI patterns such as overly generic language, repetitive sentence structures, and lack of genuine personal experiences."
            else:
                return "The post appears to be human-written based on its natural language patterns, personal anecdotes, and authentic writing style."

        if "sure" in message_lower or "confident" in message_lower:
            return f"The confidence level for this analysis is {(post.confidence * 100):.1f}%. This is based on multiple factors including language patterns, content structure, and stylistic elements."

        if "false positive" in message_lower:
            return "While our AI detection system is highly accurate, false positives can occur. Human writing that is very formal, uses common phrases, or follows predictable patterns might be mistakenly flagged. If you believe this is incorrect, you can choose to ignore this analysis."

        # Default response
        return "I can help you understand the AI detection analysis for this post. The system has analyzed various aspects of the content including writing style, language patterns, and structural elements. Feel free to ask specific questions about the analysis."

    def _generate_suggested_questions(self, post: Post, chat_history: List[Chat]) -> List[str]:
        """Generate suggested follow-up questions."""
        questions = [
            "What specific patterns indicate this is AI-generated?",
            "How confident are you in this analysis?",
            "Could this be a false positive?",
            "What are the key indicators of AI-generated content?",
        ]

        if post.verdict == "ai_slop":
            questions.append("What makes this different from human writing?")
        else:
            questions.append("Why do you think this is human-written?")

        # Filter out questions that have already been asked
        asked_questions = {chat.message.lower() for chat in chat_history if chat.role == "user"}
        available_questions = [q for q in questions if q.lower() not in asked_questions]

        # Return top 3 questions
        return available_questions[:3]
