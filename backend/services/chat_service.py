"""Chat service for Google Gemini integration with concurrency control and retries."""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from core.config import settings
from db.models import Chat, Post, PostMedia, User
from schemas.chat import ChatRequest, ChatResponse, Message
from services.gemini_on_demand_service import gemini_on_demand_service
from utils.logging import get_logger

logger = get_logger(__name__)


class Role(str, Enum):
    user = "user"
    assistant = "assistant"


class ChatService:
    """Service for managing chat conversations about posts using Google Gemini."""

    def __init__(self):
        """Initialize the chat service and concurrency controls."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for chat functionality")

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

        # Concurrency limiter for Gemini calls
        self._sem = asyncio.Semaphore(settings.gemini_max_concurrency)

    # --- Singleton support ---
    _instance: Optional["ChatService"] = None
    _instance_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_instance_async(cls) -> "ChatService":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = ChatService()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ChatService":
        # Synchronous accessor for modules that import at startup
        if cls._instance is None:
            cls._instance = ChatService()
        return cls._instance

    # --- Internal helpers: retries, concurrency, history building ---

    async def _with_limit_and_timeout(self, func, *args, timeout: Optional[float] = None, **kwargs):
        """Run a blocking func in a thread with concurrency + timeout.

        Args:
            func: Callable to execute in a thread
            *args: Positional args for the callable
            timeout: Optional timeout override in seconds
            **kwargs: Keyword args for the callable

        Returns:
            Result of the callable
        """
        effective_timeout = timeout if timeout is not None else settings.gemini_timeout_seconds
        async with self._sem:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError as e:
                # Provide a clear, non-empty message for upstream handlers
                raise asyncio.TimeoutError(f"Gemini call timed out after {effective_timeout:.0f}s") from e

    async def _retry(self, coro_fn, *args, **kwargs):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.gemini_retry_max_attempts),
            wait=wait_exponential(multiplier=settings.gemini_retry_backoff_base, min=0.5, max=8),
            reraise=True,
        ):
            with attempt:
                return await coro_fn(*args, **kwargs)

    async def _gemini_send_message(self, chat_session, content, *, timeout: Optional[float] = None):
        return await self._with_limit_and_timeout(chat_session.send_message, content, timeout=timeout)

    async def _gemini_get_file(self, file_name: str):
        return await self._with_limit_and_timeout(genai.get_file, file_name)

    def _to_gemini_history(self, chats: List[Chat]) -> List[dict]:
        history = []
        for chat in chats:
            role = "model" if chat.role == Role.assistant.value else "user"
            history.append({"role": role, "parts": [chat.message]})
        return history

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
        # Validate message
        if not request.message or not request.message.strip():
            raise ValueError("Message must not be empty")

        # Get or create user
        user = await self._get_or_create_user(request.user_id, db)

        # Get post from database
        post = await self._get_post(request.post_id, db)
        if not post:
            raise ValueError(f"Post with ID {request.post_id} not found")

        # Get user-specific chat history
        chat_history = await self._get_user_chat_history(post.post_id, user.id, db)

        # Ensure media Gemini URIs, preferring stored URIs first
        file_uris: List[str] = await self._get_post_gemini_file_uris(post.post_id, db)
        if not file_uris:
            if not chat_history:
                media_urls = await self._get_all_media_urls_for_post(post.post_id, db)
                if media_urls:
                    file_uris = await gemini_on_demand_service.batch_ensure_gemini_uris(post.post_id, media_urls, db)
                    logger.info(
                        "Media prepared for chat",
                        post_id=post.post_id,
                        total_media=len(media_urls),
                        gemini_ready=len(file_uris),
                    )
                else:
                    logger.info("No media found for this post", post_id=post.post_id)
            else:
                # Reuse file URIs from previous messages in this conversation
                for chat in chat_history:
                    if chat.file_uris:
                        file_uris = chat.file_uris
                        break

        # Save user message with file references
        await self._save_message(post.post_id, user.id, "user", request.message, file_uris, db)

        # Update chat history to include the new message
        chat_history = await self._get_user_chat_history(post.post_id, user.id, db)

        # Generate AI response (multimodal if images available)
        if file_uris:
            # Cap media parts to control latency/cost
            capped_uris = file_uris[: settings.gemini_max_media_files]
            response_text = await self._generate_multimodal_response(post, request.message, chat_history, capped_uris)
        else:
            response_text = await self._generate_response(post, request.message, chat_history)

        # Save AI response
        assistant_chat = await self._save_message(post.post_id, user.id, "assistant", response_text, [], db)

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
        Get chat history for a post (all users - legacy method).

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

    async def get_user_chat_history(
        self,
        post_id: str,
        user_identifier: str,
        db: AsyncSession,
    ) -> List[Message]:
        """
        Get user-specific chat history for a post.

        Args:
            post_id: Facebook post ID
            user_identifier: Browser user identifier
            db: Database session

        Returns:
            List of chat messages for this specific user
        """
        # Get post from database
        post = await self._get_post(post_id, db)
        if not post:
            raise ValueError(f"Post with ID {post_id} not found")

        # Get user (readonly - no creation for history retrieval)
        user = await self._get_user_readonly(user_identifier, db)
        if not user:
            # No user exists, so no chat history
            return []

        # Get user-specific chat history
        chats = await self._get_user_chat_history(post.post_id, user.id, db)

        return [
            Message(
                id=chat.id,
                role=chat.role,
                message=chat.message,
                created_at=chat.created_at.isoformat(),
            )
            for chat in chats
        ]

    async def _get_or_create_user(self, user_id: str, db: AsyncSession) -> User:
        """Get or create user by ID."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=user_id,
                last_active_at=datetime.now(timezone.utc),
            )
            db.add(user)
        else:
            # Update last active timestamp
            user.last_active_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)
        return user

    async def _get_user_readonly(self, user_id: str, db: AsyncSession) -> Optional[User]:
        """Get user without creating or updating it (for history retrieval)."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _get_user_chat_history(self, post_id: str, user_id: str, db: AsyncSession, limit: int = 20) -> List[Chat]:
        """Get chat history for a specific user and post."""
        result = await db.execute(
            select(Chat).where(Chat.post_id == post_id).where(Chat.user_id == user_id).order_by(Chat.created_at.asc()).limit(limit)
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

    async def _get_all_media_urls_for_post(self, post_id: str, db: AsyncSession) -> List[str]:
        """Get all media URLs for a post (both images and videos)."""
        result = await db.execute(select(PostMedia.media_url).where(PostMedia.post_id == post_id))
        return [url for (url,) in result.fetchall()]

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
        result = await db.execute(select(Post).where(Post.post_id == post_id))
        return result.scalar_one_or_none()

    async def _get_chat_history(self, post_id: str, db: AsyncSession, limit: int = 20) -> List[Chat]:
        """Get chat history for a post."""
        result = await db.execute(select(Chat).where(Chat.post_id == post_id).order_by(Chat.created_at.asc()).limit(limit))
        return result.scalars().all()

    async def _save_message(
        self,
        post_id: str,
        user_id: str,
        role: str,
        message: str,
        file_uris: List[str],
        db: AsyncSession,
    ) -> Chat:
        """Save a chat message to database with user and file references."""
        chat = Chat(
            id=str(uuid.uuid4()),
            post_id=post_id,
            user_id=user_id,
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

Special guidance for specific questions:
- When asked "Why should I avoid these posts?": Explain AI slop harms including misinformation spread, time-wasting clickbait, degraded information quality, manipulation tactics, and how AI-generated content reduces meaningful engagement and critical thinking
- When asked "How can I avoid having these in my Facebook?": Provide actionable advice like clicking "Not Interested" on similar posts, unfollowing sources that post AI slop frequently, adjusting Facebook feed preferences, engaging less with low-quality content, and being selective about interactions

Keep responses informative but concise (2-4 sentences typically)."""

            # Initialize model with the specific post context
            model = genai.GenerativeModel(
                "gemini-2.5-flash-lite",
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 0.6,
                    "top_p": 0.95,
                    "max_output_tokens": 512,
                },
            )
            # Build history excluding the just-saved current message
            history = self._to_gemini_history(chat_history[:-1])
            chat_session = model.start_chat(history=history)

            # Send the current user message and get response (with retries/timeout/concurrency)
            response = await self._retry(self._gemini_send_message, chat_session, user_message)
            return response.text

        except Exception as e:
            logger.error(
                "Error generating Gemini response",
                error=str(e) or e.__class__.__name__,
                post_id=post.post_id,
                user_message=user_message[:100] + "..." if len(user_message) > 100 else user_message,
                exc_info=True,
            )
            err_msg = str(e) or e.__class__.__name__
            raise Exception(f"Failed to generate chat response: {err_msg}")

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

Special guidance for specific questions:
- When asked "Why should I avoid these posts?": Explain AI slop harms including misinformation spread, time-wasting clickbait, degraded information quality, manipulation tactics, and how AI-generated content reduces meaningful engagement and critical thinking
- When asked "How can I avoid having these in my Facebook?": Provide actionable advice like clicking "Not Interested" on similar posts, unfollowing sources that post AI slop frequently, adjusting Facebook feed preferences, engaging less with low-quality content, and being selective about interactions

Keep responses informative but concise (2-4 sentences typically)."""

            # Initialize model with multimodal capability
            model = genai.GenerativeModel(
                "gemini-2.5-flash-lite",
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 0.6,
                    "top_p": 0.95,
                    "max_output_tokens": 512,
                },
            )

            # Build history excluding the current message
            history = self._to_gemini_history(chat_history[:-1])
            chat_session = model.start_chat(history=history)

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

                    file = await self._retry(self._gemini_get_file, file_name)
                    prompt_parts.append(file)
                    logger.info("Successfully loaded media file for multimodal prompt", uri=uri, file_name=file_name)
                except Exception as e:
                    logger.warning("Failed to load media file for multimodal prompt", uri=uri, error=str(e))

            # Add current user message
            prompt_parts.append(f"User question: {user_message}")

            # Generate response with multimodal content
            # Multimodal generations often take longer; allow an explicit configurable timeout.
            # Use GEMINI_MULTIMODAL_TIMEOUT_SECONDS if set; else fall back to GEMINI_TIMEOUT_SECONDS.
            multi_timeout = getattr(settings, "gemini_multimodal_timeout_seconds", None) or settings.gemini_timeout_seconds

            response = await self._retry(
                self._gemini_send_message,
                chat_session,
                prompt_parts,
                timeout=multi_timeout,
            )
            return response.text

        except Exception as e:
            logger.error(
                "Error generating multimodal Gemini response",
                error=str(e) or e.__class__.__name__,
                post_id=post.post_id,
                user_message=user_message[:100] + "..." if len(user_message) > 100 else user_message,
                media_file_count=len(file_uris),
                exc_info=True,
            )
            err_msg = str(e) or e.__class__.__name__
            raise Exception(f"Failed to generate multimodal chat response: {err_msg}")

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
            system_instruction = f"""You are an AI assistant helping generate intelligent follow-up questions for users who want to understand AI content detection results and learn about AI slop harms.

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
1. Build naturally on the conversation without repeating previously discussed topics
2. Help the user better understand the detection results AND the broader implications of AI slop
3. Encourage awareness of AI slop harms such as attention drain, misinformation spillover, trust erosion, cultural distortion, or algorithmic pollution
4. Are specific to this post's content and analysis results
5. Are conversational and engaging
6. Keep each question under 8 words when possible
7. Use simple, direct language

PRIORITIZE these harm-awareness questions when relevant and not yet explored:
- "Why should I avoid these posts?" - Focus on AI slop harms: attention drain, misinformation spillover, trust erosion, cultural distortion, algorithmic pollution, time-wasting clickbait, and degraded information quality
- "How can I avoid having these in my Facebook?" - Provide actionable advice: clicking "Not Interested", unfollowing AI slop sources, adjusting feed preferences, reducing engagement with low-quality content
- "What harm does AI slop cause?" - Explain broader impacts on society, information quality, and user well-being
- "How does this affect my feed quality?" - Discuss algorithmic pollution and degraded user experience
- "Why is this spreading so much?" - Address cultural distortion and economic incentives behind AI slop

For AI-generated content, also consider:
- "What makes this feel manipulative?"
- "How does this waste my time?"
- "What's the real agenda here?"

Do not ask questions which have been asked before in the conversation history.

Return ONLY the 3 questions, each on a separate line, without numbers or bullet points."""

            # Initialize model
            model = genai.GenerativeModel(
                "gemini-2.5-flash-lite",
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 0.6,
                    "top_p": 0.95,
                    "max_output_tokens": 128,
                },
            )

            # Generate suggestions with concurrency limit, timeout, and retries
            response = await self._retry(
                self._with_limit_and_timeout,
                model.generate_content,
                "Generate 3 intelligent follow-up questions based on the context above.",
            )

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
        """Generate fallback suggestions when Gemini fails, focusing on AI slop harms awareness."""
        # Prioritize harm-awareness questions
        harm_awareness_questions = [
            "Why should I avoid these posts?",
            "How can I avoid having these in my Facebook?",
            "What harm does AI slop cause?",
            "How does this affect my feed quality?",
            "Why is this spreading so much?",
        ]

        # Technical analysis questions
        technical_questions = [
            "What patterns suggest AI generation?",
            "How confident is this analysis?",
            "Could this be wrong?",
            "What are the key indicators?",
        ]

        # Context-specific questions for AI slop
        if post.verdict == "ai_slop":
            ai_specific_questions = [
                "What makes this feel manipulative?",
                "How does this waste my time?",
                "What's the real agenda here?",
                "How is this different from human writing?",
            ]
        else:
            ai_specific_questions = [
                "Why is this human-written?",
                "What makes authentic content different?",
            ]

        # Combine all questions, prioritizing harm awareness
        questions = harm_awareness_questions + ai_specific_questions + technical_questions

        # Return top 3 questions
        # Note: For fallback suggestions, we don't filter by conversation history
        # since the main Gemini-based suggestion generation handles conversation
        # awareness more effectively. This fallback is only used when Gemini fails.
        return questions[:3]

    def _generate_suggested_questions(self, post: Post, chat_history: List[Chat]) -> List[str]:
        """Generate suggested follow-up questions (legacy method, kept for compatibility)."""
        return self._generate_fallback_suggestions(post, chat_history)


# Module-level singleton for injection in routes
chat_service = ChatService.get_instance()
