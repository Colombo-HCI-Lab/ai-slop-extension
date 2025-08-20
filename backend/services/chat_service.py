"""Chat service for Google Gemini integration."""

import logging
import uuid
from typing import List, Optional

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from models import Chat, Post
from schemas.chat import ChatRequest, ChatResponse, Message

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat conversations about posts using Google Gemini."""

    def __init__(self):
        """Initialize the chat service."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for chat functionality")

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

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
        await self._save_message(post.id, "user", request.message, db)

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
        """Generate AI response using Gemini with comprehensive context."""
        try:
            # Build comprehensive detection results summary
            detection_summary = self._build_detection_summary(post)
            
            # Create system instruction with post content and detection results
            system_instruction = f"""You are an expert AI content detection assistant helping users understand detection results for this specific social media post.

POST CONTENT:
"{post.content}"

AUTHOR: {post.author or "Unknown"}

DETECTION ANALYSIS RESULTS:
{detection_summary}

OVERALL VERDICT: {post.verdict}
OVERALL CONFIDENCE: {(post.confidence * 100):.1f}%
EXPLANATION: {post.explanation or "No detailed explanation provided"}

Your role:
- Help users understand these specific AI detection results
- Explain the reasoning behind the analysis in an accessible way
- Answer questions about the detection methods (text analysis, image detection, video analysis)
- Reference the actual post content when relevant
- Be conversational and engaging, not robotic
- Acknowledge limitations and potential for false positives/negatives
- Provide insights based on the specific detection scores and confidence levels shown above

Keep responses informative but concise (2-4 sentences typically)."""

            # Initialize model with the specific post context
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
            chat_session = model.start_chat()
            
            # Add previous conversation history
            for chat in chat_history[:-1]:  # Exclude the current message we just saved
                if chat.role == "user":
                    # Send user message
                    chat_session.send_message(chat.message)
                elif chat.role == "assistant":
                    # For assistant messages, we need to simulate the response
                    # Since Gemini tracks assistant responses automatically, we skip this
                    pass
            
            # Send the current user message and get response
            response = chat_session.send_message(user_message)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            raise Exception(f"Failed to generate chat response: {str(e)}")

    def _build_detection_summary(self, post: Post) -> str:
        """Build a comprehensive summary of all detection results."""
        summary_parts = []
        
        # Text detection results
        if post.text_ai_probability is not None:
            text_status = "AI-generated" if post.text_ai_probability > 0.5 else "Human-written"
            summary_parts.append(f"Text Analysis: {text_status} (probability: {post.text_ai_probability:.3f}, confidence: {post.text_confidence or 0:.3f})")
        
        # Image detection results
        if post.image_ai_probability is not None:
            image_status = "AI-generated" if post.image_ai_probability > 0.5 else "Human-created"
            summary_parts.append(f"Image Analysis: {image_status} (probability: {post.image_ai_probability:.3f}, confidence: {post.image_confidence or 0:.3f})")
        
        # Video detection results
        if post.video_ai_probability is not None:
            video_status = "AI-generated" if post.video_ai_probability > 0.5 else "Human-created"
            summary_parts.append(f"Video Analysis: {video_status} (probability: {post.video_ai_probability:.3f}, confidence: {post.video_confidence or 0:.3f})")
        
        # Add metadata if available
        if post.post_metadata:
            metadata_summary = ", ".join([f"{k}: {v}" for k, v in post.post_metadata.items()])
            summary_parts.append(f"Additional Metadata: {metadata_summary}")
        
        return "\n".join(summary_parts) if summary_parts else "No detailed detection results available"


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
