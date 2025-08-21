"""Chat service for Google Gemini integration."""

import uuid
from datetime import datetime
from typing import List, Optional, Tuple

import google.generativeai as genai
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from models import Chat, Post, PostMedia, UserSession
from schemas.chat import ChatRequest, ChatResponse, Message
from services.file_upload_service import FileUploadService
from utils.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """Service for managing chat conversations about posts using Google Gemini."""

    def __init__(self):
        """Initialize the chat service."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for chat functionality")

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

        # Initialize file upload service
        self.file_service = FileUploadService()

    async def send_message(
        self,
        request: ChatRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        """
        Send a message about a post and get AI response with multimodal support.

        Args:
            request: Chat request with post ID, message, user ID, and optional images
            db: Database session

        Returns:
            Chat response with AI-generated reply
        """
        # Get or create user session
        user_session = await self._get_or_create_user_session(request.user_id, db)

        # Get post from database
        post = await self._get_post(request.post_id, db)
        if not post:
            raise ValueError(f"Post with ID {request.post_id} not found")

        # Get user-specific chat history
        chat_history = await self._get_user_chat_history(post.post_id, user_session.id, db)

        # Get pre-uploaded Gemini file URIs for first message in conversation
        file_uris = []
        if not chat_history:
            # First message in conversation - get pre-uploaded Gemini file URIs from database
            file_uris = await self._get_post_gemini_file_uris(post.post_id, db)
            if file_uris:
                logger.info(f"Using {len(file_uris)} pre-uploaded Gemini file URIs for new conversation", post_id=post.post_id)
            else:
                # Check if post media exists but Gemini URIs are not set
                media_count = await self._get_post_media_count(post.post_id, db)
                if media_count > 0:
                    logger.warning(f"Post has {media_count} media files but no Gemini file URIs found", post_id=post.post_id)
                else:
                    logger.info("No media found for this post", post_id=post.post_id)
        else:
            # Reuse file URIs from previous messages in this conversation
            for chat in chat_history:
                if chat.file_uris:
                    file_uris = chat.file_uris
                    break

        # Save user message with file references
        await self._save_message(post.post_id, user_session.id, "user", request.message, file_uris, db)

        # Update chat history to include the new message
        chat_history = await self._get_user_chat_history(post.post_id, user_session.id, db)

        # Generate AI response (multimodal if images available)
        if file_uris:
            response_text = await self._generate_multimodal_response(post, request.message, chat_history, file_uris)
        else:
            response_text = await self._generate_response(post, request.message, chat_history)

        # Save AI response
        assistant_chat = await self._save_message(post.post_id, user_session.id, "assistant", response_text, [], db)

        # Generate suggested questions using Gemini
        suggested_questions = await self._generate_gemini_suggestions(post, chat_history)

        # Count media types in file URIs (rough estimation based on typical naming)
        media_sources = []
        if file_uris:
            # Check if we have media based on database info
            image_urls, video_urls = await self._get_post_media_urls(post.post_id, db)
            if image_urls:
                media_sources.append("Image analysis")
            if video_urls:
                media_sources.append("Video analysis")

        return ChatResponse(
            id=assistant_chat.id,
            message=response_text,
            suggested_questions=suggested_questions,
            context={
                "sources": ["Content analysis", "Pattern recognition", "Language modeling"] + media_sources,
                "confidence": post.confidence,
                "has_images": len(file_uris) > 0,
                "media_count": len(file_uris),
                "additional_info": "This analysis includes text and multimedia content"
                if file_uris
                else "This analysis is based on text content patterns",
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
        chats = await self._get_chat_history(post.post_id, db)

        return [
            Message(
                id=chat.id,
                role=chat.role,
                message=chat.message,
                created_at=chat.created_at.isoformat(),
            )
            for chat in chats
        ]

    async def _get_or_create_user_session(self, user_identifier: str, db: AsyncSession) -> UserSession:
        """Get or create user session by identifier."""
        result = await db.execute(select(UserSession).where(UserSession.user_identifier == user_identifier))
        user_session = result.scalar_one_or_none()

        if not user_session:
            user_session = UserSession(
                id=str(uuid.uuid4()),
                user_identifier=user_identifier,
                last_active=datetime.now(),
            )
            db.add(user_session)
        else:
            # Update last active timestamp
            await db.execute(update(UserSession).where(UserSession.id == user_session.id).values(last_active=datetime.now()))

        await db.commit()
        await db.refresh(user_session)
        return user_session

    async def _get_user_chat_history(self, post_id: str, user_session_id: str, db: AsyncSession, limit: int = 20) -> List[Chat]:
        """Get chat history for a specific user and post."""
        result = await db.execute(
            select(Chat)
            .where(Chat.post_id == post_id)
            .where(Chat.user_session_id == user_session_id)
            .order_by(Chat.created_at.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def _get_post_image_urls(self, post_id: str, db: AsyncSession) -> List[str]:
        """Get image URLs from post media table."""
        result = await db.execute(select(PostMedia.media_url).where(PostMedia.post_id == post_id).where(PostMedia.media_type == "image"))
        return [url for (url,) in result.fetchall()]

    async def _get_post_video_urls(self, post_id: str, db: AsyncSession) -> List[str]:
        """Get video URLs from post media table."""
        result = await db.execute(select(PostMedia.media_url).where(PostMedia.post_id == post_id).where(PostMedia.media_type == "video"))
        return [url for (url,) in result.fetchall()]

    async def _get_post_media_urls(self, post_id: str, db: AsyncSession) -> Tuple[List[str], List[str]]:
        """Get both image and video URLs from post media table."""
        image_urls = await self._get_post_image_urls(post_id, db)
        video_urls = await self._get_post_video_urls(post_id, db)
        return image_urls, video_urls

    async def _get_post_gemini_file_uris(self, post_id: str, db: AsyncSession) -> List[str]:
        """Get pre-uploaded Gemini file URIs from post media table."""
        result = await db.execute(
            select(PostMedia.gemini_file_uri).where(PostMedia.post_id == post_id).where(PostMedia.gemini_file_uri.isnot(None))
        )
        return [uri for (uri,) in result.fetchall() if uri]

    async def _get_post_media_count(self, post_id: str, db: AsyncSession) -> int:
        """Get count of media files for a post."""
        from sqlalchemy import func

        result = await db.execute(select(func.count(PostMedia.id)).where(PostMedia.post_id == post_id))
        return result.scalar() or 0

    async def _get_post(self, post_id: str, db: AsyncSession) -> Optional[Post]:
        """Get post by Facebook post ID."""
        result = await db.execute(select(Post).where(Post.post_id == post_id).options(selectinload(Post.chats)))
        return result.scalar_one_or_none()

    async def _get_chat_history(self, post_id: str, db: AsyncSession, limit: int = 20) -> List[Chat]:
        """Get chat history for a post."""
        result = await db.execute(select(Chat).where(Chat.post_id == post_id).order_by(Chat.created_at.asc()).limit(limit))
        return result.scalars().all()

    async def _save_message(
        self,
        post_id: str,
        user_session_id: str,
        role: str,
        message: str,
        file_uris: List[str],
        db: AsyncSession,
    ) -> Chat:
        """Save a chat message to database with user session and file references."""
        chat = Chat(
            id=str(uuid.uuid4()),
            post_id=post_id,
            user_session_id=user_session_id,
            role=role,
            message=message,
            file_uris=file_uris if file_uris else None,
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
            logger.error(
                "Error generating Gemini response",
                error=str(e),
                post_id=post.post_id,
                user_message=user_message[:100] + "..." if len(user_message) > 100 else user_message,
                exc_info=True,
            )
            raise Exception(f"Failed to generate chat response: {str(e)}")

    async def _generate_multimodal_response(self, post: Post, user_message: str, chat_history: List[Chat], file_uris: List[str]) -> str:
        """Generate AI response using Gemini with text, images, and videos."""
        try:
            # Build comprehensive detection results summary
            detection_summary = self._build_detection_summary(post)

            # Create system instruction with post content and image context
            system_instruction = f"""You are an expert AI content detection assistant helping users understand detection results for this specific social media post.

POST CONTENT:
"{post.content}"

AUTHOR: {post.author or "Unknown"}

DETECTION ANALYSIS RESULTS:
{detection_summary}

OVERALL VERDICT: {post.verdict}
OVERALL CONFIDENCE: {(post.confidence * 100):.1f}%
EXPLANATION: {post.explanation or "No detailed explanation provided"}

MULTIMEDIA CONTENT: You have access to {len(file_uris)} media files (images and/or videos) from this post. Analyze them for:
- Visual signs of AI generation (artifacts, inconsistencies, unnatural elements)
- For videos: motion patterns, temporal consistency, audio-visual synchronization
- Correlation between text claims and visual/video content
- Overall authenticity assessment combining text and multimedia evidence

Your role:
- Help users understand these specific AI detection results
- Analyze both text and visual content for comprehensive insights
- Explain the reasoning behind the analysis in an accessible way
- Reference specific visual elements when relevant
- Be conversational and engaging, not robotic
- Acknowledge limitations and potential for false positives/negatives
- Provide insights based on the specific detection scores and confidence levels shown above

Keep responses informative but concise (2-4 sentences typically)."""

            # Initialize model with multimodal capability
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
            chat_session = model.start_chat()

            # Create multimodal prompt with images
            prompt_parts = []

            # Add images first
            for uri in file_uris:
                try:
                    # Extract file name from URI if needed
                    if uri.startswith("https://generativelanguage.googleapis.com/v1beta/files/"):
                        file_name = uri.split("/files/")[-1]
                    else:
                        file_name = uri

                    file = genai.get_file(file_name)
                    prompt_parts.append(file)
                    logger.info("Successfully loaded media file for multimodal prompt", uri=uri, file_name=file_name)
                except Exception as e:
                    logger.warning("Failed to load media file for multimodal prompt", uri=uri, error=str(e))

            # Add conversation history
            for chat in chat_history[:-1]:  # Exclude the current message we just saved
                if chat.role == "user":
                    chat_session.send_message(chat.message)

            # Add current user message
            prompt_parts.append(f"User question: {user_message}")

            # Generate response with multimodal content
            response = chat_session.send_message(prompt_parts)
            return response.text

        except Exception as e:
            logger.error(
                "Error generating multimodal Gemini response",
                error=str(e),
                post_id=post.post_id,
                user_message=user_message[:100] + "..." if len(user_message) > 100 else user_message,
                media_file_count=len(file_uris),
                exc_info=True,
            )
            raise Exception(f"Failed to generate multimodal chat response: {str(e)}")

    def _build_detection_summary(self, post: Post) -> str:
        """Build a comprehensive summary of all detection results."""
        summary_parts = []

        # Text detection results
        if post.text_ai_probability is not None:
            text_status = "AI-generated" if post.text_ai_probability > 0.5 else "Human-written"
            summary_parts.append(
                f"Text Analysis: {text_status} (probability: {post.text_ai_probability:.3f}, confidence: {post.text_confidence or 0:.3f})"
            )

        # Image detection results
        if post.image_ai_probability is not None:
            image_status = "AI-generated" if post.image_ai_probability > 0.5 else "Human-created"
            summary_parts.append(
                f"Image Analysis: {image_status} (probability: {post.image_ai_probability:.3f}, confidence: {post.image_confidence or 0:.3f})"
            )

        # Video detection results
        if post.video_ai_probability is not None:
            video_status = "AI-generated" if post.video_ai_probability > 0.5 else "Human-created"
            summary_parts.append(
                f"Video Analysis: {video_status} (probability: {post.video_ai_probability:.3f}, confidence: {post.video_confidence or 0:.3f})"
            )

        # Add metadata if available
        if post.post_metadata:
            metadata_summary = ", ".join([f"{k}: {v}" for k, v in post.post_metadata.items()])
            summary_parts.append(f"Additional Metadata: {metadata_summary}")

        return "\n".join(summary_parts) if summary_parts else "No detailed detection results available"

    async def _generate_gemini_suggestions(self, post: Post, chat_history: List[Chat]) -> List[str]:
        """Generate intelligent question suggestions using Gemini AI."""
        try:
            # Build comprehensive detection results summary
            detection_summary = self._build_detection_summary(post)

            # Create conversation history summary
            conversation_summary = ""
            if chat_history:
                conversation_summary = "\n\nCONVERSATION HISTORY:\n"
                for chat in chat_history:
                    conversation_summary += f"{chat.role.upper()}: {chat.message}\n"
            else:
                conversation_summary = "\n\nCONVERSATION HISTORY: No previous conversation"

            # Create system instruction for generating suggestions
            system_instruction = f"""You are an AI assistant helping generate intelligent follow-up questions for users who want to understand AI content detection results.

POST CONTENT:
"{post.content}"

AUTHOR: {post.author or "Unknown"}

DETECTION ANALYSIS RESULTS:
{detection_summary}

OVERALL VERDICT: {post.verdict}
OVERALL CONFIDENCE: {(post.confidence * 100):.1f}%
EXPLANATION: {post.explanation or "No detailed explanation provided"}
{conversation_summary}

Generate 3 short, concise follow-up questions that:
1. Haven't been asked before in the conversation history
2. Help the user better understand the detection results
3. Explore different aspects of AI detection (patterns, confidence, methodology, implications)
4. Are specific to this post's content and analysis results
5. Are conversational and engaging
6. Keep each question under 8 words when possible
7. Use simple, direct language

Return ONLY the 3 questions, each on a separate line, without numbers or bullet points."""

            # Initialize model
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)

            # Generate suggestions
            response = model.generate_content("Generate 3 intelligent follow-up questions based on the context above.")

            # Parse response into individual questions
            questions = [q.strip() for q in response.text.strip().split("\n") if q.strip()]

            # Ensure we have exactly 3 questions
            if len(questions) > 3:
                questions = questions[:3]
            elif len(questions) < 3:
                # Fallback to basic questions if needed
                fallback_questions = [
                    "What patterns suggest AI generation?",
                    "How confident is this analysis?",
                    "Could this be wrong?",
                ]
                questions.extend(fallback_questions[len(questions) : 3])

            return questions

        except Exception as e:
            logger.error(
                "Error generating Gemini suggestions",
                error=str(e),
                post_id=post.post_id,
                exc_info=True,
            )
            # Fallback to basic suggestions
            return self._generate_fallback_suggestions(post, chat_history)

    def _generate_fallback_suggestions(self, post: Post, chat_history: List[Chat]) -> List[str]:
        """Generate fallback suggestions when Gemini fails."""
        questions = [
            "What patterns suggest AI generation?",
            "How confident is this analysis?",
            "Could this be wrong?",
            "What are the key indicators?",
        ]

        if post.verdict == "ai_slop":
            questions.append("How is this different from human writing?")
        else:
            questions.append("Why is this human-written?")

        # Filter out questions that have already been asked
        asked_questions = {chat.message.lower() for chat in chat_history if chat.role == "user"}
        available_questions = [q for q in questions if q.lower() not in asked_questions]

        # Return top 3 questions
        return available_questions[:3]

    def _generate_suggested_questions(self, post: Post, chat_history: List[Chat]) -> List[str]:
        """Generate suggested follow-up questions (legacy method, kept for compatibility)."""
        return self._generate_fallback_suggestions(post, chat_history)
