"""Post summary service for generating AI-powered content summaries using Gemini."""

import asyncio
from typing import List, Optional, Tuple

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from core.config import settings
from db.models import Post, PostMedia
from utils.logging import get_logger

logger = get_logger(__name__)


class PostSummaryService:
    """Service for generating AI-powered summaries of posts using Google Gemini."""

    def __init__(self):
        """Initialize the post summary service."""
        self._initialized = False
        self._initialization_error = None

        try:
            # Check for API key
            api_key = getattr(settings, "gemini_api_key", None)
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY is required for post summary functionality. Please set the GEMINI_API_KEY environment variable."
                )

            # Check API key format (basic validation)
            if not isinstance(api_key, str) or len(api_key) < 10:
                raise ValueError("GEMINI_API_KEY appears to be invalid (too short or wrong type)")

            # Configure Gemini API
            genai.configure(api_key=api_key)
            logger.debug("Gemini API configured with key", key_length=len(api_key), key_prefix=api_key[:8] + "...")

            # Set up concurrency control
            max_concurrency = getattr(settings, "gemini_max_concurrency", 3)
            self._sem = asyncio.Semaphore(max_concurrency)

            self._initialized = True
            logger.info(
                "PostSummaryService initialized successfully",
                gemini_api_key_length=len(api_key),
                max_concurrency=max_concurrency,
            )

        except Exception as e:
            self._initialization_error = e
            logger.error(
                "PostSummaryService initialization failed - will use fallback summaries",
                error=str(e),
                error_type=type(e).__name__,
                has_gemini_key=bool(getattr(settings, "gemini_api_key", None)),
                gemini_key_length=len(getattr(settings, "gemini_api_key", "") or ""),
                exc_info=True,
            )
            # Don't raise the exception - allow the service to be created but mark it as failed

    # --- Singleton support ---
    _instance: Optional["PostSummaryService"] = None
    _instance_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_instance_async(cls) -> "PostSummaryService":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = PostSummaryService()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "PostSummaryService":
        # Synchronous accessor for modules that import at startup
        if cls._instance is None:
            cls._instance = PostSummaryService()
        return cls._instance

    async def generate_summaries(self, post: Post, db: AsyncSession) -> Tuple[str, str, str]:
        """
        Generate AI-powered summaries for a post. Always returns valid summaries.

        Args:
            post: Post object with content and detection results
            db: Database session

        Returns:
            Tuple of (gen_short_title, gen_title, gen_description) - guaranteed non-empty
        """
        logger.info(
            "Starting summary generation",
            post_id=post.post_id,
            content_length=len(post.content),
            verdict=post.verdict,
            confidence=round(post.confidence, 3),
            service_initialized=self._initialized,
        )

        # Check if service was properly initialized
        if not self._initialized:
            logger.error(
                "PostSummaryService not properly initialized, using fallback summaries",
                post_id=post.post_id,
                initialization_error=str(self._initialization_error) if self._initialization_error else "Unknown",
                has_gemini_key=bool(getattr(settings, "gemini_api_key", None)),
            )
            return self._generate_fallback_summaries(post)

        try:
            # Get media URLs for multimodal analysis
            file_uris = await self._get_post_gemini_file_uris(post.post_id, db)
            logger.debug(
                "Media URIs retrieved for summary generation",
                post_id=post.post_id,
                media_count=len(file_uris),
            )

            # Generate summaries based on whether we have media or not
            if file_uris:
                logger.info("Using multimodal summary generation", post_id=post.post_id, media_count=len(file_uris))
                short_title, title, description = await self._generate_multimodal_summaries(post, file_uris)
            else:
                logger.info("Using text-only summary generation", post_id=post.post_id)
                short_title, title, description = await self._generate_text_only_summaries(post)

            # Validate and ensure non-empty summaries
            short_title, title, description = self._validate_summaries(short_title, title, description, post)

            logger.info(
                "Summary generation completed successfully",
                post_id=post.post_id,
                short_title_length=len(short_title),
                title_length=len(title),
                description_length=len(description),
                used_media=bool(file_uris),
            )

            return short_title, title, description

        except Exception as e:
            logger.error(
                "Error generating post summaries, using fallback",
                post_id=post.post_id,
                error=str(e),
                exc_info=True,
            )
            # Return guaranteed valid fallback summaries
            short_title, title, description = self._generate_fallback_summaries(post)

            logger.warning(
                "Using fallback summaries due to generation error",
                post_id=post.post_id,
                short_title=short_title,
                title_length=len(title),
                description_length=len(description),
            )

            return short_title, title, description

    def _validate_summaries(self, short_title: str, title: str, description: str, post: Post) -> Tuple[str, str, str]:
        """
        Validate and ensure all summaries are non-empty and within length limits.

        Args:
            short_title: Generated short title
            title: Generated title
            description: Generated description
            post: Post object for fallback generation

        Returns:
            Tuple of validated (short_title, title, description)
        """
        warnings = []

        # Validate short_title
        if not short_title or not short_title.strip():
            warnings.append("short_title is empty")
            short_title = self._extract_short_title_from_content(post.content)
        else:
            short_title = short_title.strip()[:100]  # Ensure within database limit

        # Validate title
        if not title or not title.strip():
            warnings.append("title is empty")
            title = self._extract_title_from_content(post.content)
        else:
            title = title.strip()[:500]  # Ensure within database limit

        # Validate description
        if not description or not description.strip():
            warnings.append("description is empty")
            description = self._generate_fallback_description(post)
        else:
            description = description.strip()

        # Log warnings if any field was invalid
        if warnings:
            logger.warning(
                "Summary validation issues detected, used fallback values",
                post_id=post.post_id,
                invalid_fields=warnings,
                final_short_title_length=len(short_title),
                final_title_length=len(title),
                final_description_length=len(description),
            )

        return short_title, title, description

    async def _generate_text_only_summaries(self, post: Post) -> Tuple[str, str, str]:
        """Generate summaries using only text content and detection results."""
        logger.debug("Starting text-only summary generation", post_id=post.post_id)

        try:
            # Build detection summary
            detection_summary = self._build_detection_summary(post)

            # Create system instruction for summary generation
            system_instruction = f"""You are an expert content analyzer generating summaries for social media posts with AI detection results.

POST CONTENT:
"{post.content}"

AUTHOR: {post.author or "Unknown"}

DETECTION ANALYSIS:
{detection_summary}

OVERALL VERDICT: {post.verdict}
CONFIDENCE: {(post.confidence * 100):.1f}%
EXPLANATION: {post.explanation or "No detailed explanation provided"}

Generate three types of summaries:

1. SHORT TITLE (3-5 words): A brief identifier for quick recognition
2. TITLE (one sentence): A concise summary capturing the main point
3. DESCRIPTION (one paragraph): A detailed description including key insights and detection rationale

Focus on:
- The actual content and its main message
- Key indicators that led to the AI detection verdict
- Whether this appears to be AI-generated content or human-created
- Any notable patterns or characteristics

Be factual, clear, and concise. Avoid speculation beyond what the detection results indicate."""

            # Generate summaries with structured prompt
            model = genai.GenerativeModel(
                "gemini-2.5-flash-lite",
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_output_tokens": 400,
                },
            )

            prompt = """Generate the three summaries in this exact format:

SHORT_TITLE: [3-5 word identifier]
TITLE: [One sentence summary]
DESCRIPTION: [One paragraph description]"""

            response = await self._retry(self._gemini_generate_content, model, prompt)
            logger.debug("Text-only summary generation completed", post_id=post.post_id, response_length=len(response.text))

            # Parse the structured response
            return self._parse_summary_response(response.text, post)

        except Exception as e:
            logger.warning(
                "Text-only summary generation failed, using fallback",
                post_id=post.post_id,
                error=str(e),
            )
            return self._generate_fallback_summaries(post)

    async def _generate_multimodal_summaries(self, post: Post, file_uris: List[str]) -> Tuple[str, str, str]:
        """Generate summaries using both text content and media files."""
        logger.debug("Starting multimodal summary generation", post_id=post.post_id, media_count=len(file_uris))

        try:
            # Build detection summary
            detection_summary = self._build_detection_summary(post)

            # Create system instruction for multimodal summary generation
            system_instruction = f"""You are an expert content analyzer generating summaries for social media posts with both text and visual content, including AI detection results.

POST CONTENT:
"{post.content}"

AUTHOR: {post.author or "Unknown"}

DETECTION ANALYSIS:
{detection_summary}

OVERALL VERDICT: {post.verdict}
CONFIDENCE: {(post.confidence * 100):.1f}%
EXPLANATION: {post.explanation or "No detailed explanation provided"}

MULTIMEDIA CONTENT: You have access to {len(file_uris)} media files (images and/or videos) from this post.

Generate three types of summaries incorporating both text and visual analysis:

1. SHORT TITLE (3-5 words): A brief identifier for quick recognition
2. TITLE (one sentence): A concise summary capturing the main point of both text and visuals
3. DESCRIPTION (one paragraph): A detailed description including insights from text, visuals, and detection results

Analyze the media for:
- Visual signs of AI generation (artifacts, inconsistencies, unnatural elements)
- Correlation between text claims and visual content
- Overall authenticity assessment combining text and multimedia evidence

Be factual, clear, and concise. Reference specific visual elements when relevant."""

            # Initialize model with multimodal capability
            model = genai.GenerativeModel(
                "gemini-2.5-flash-lite",
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_output_tokens": 500,
                },
            )

            # Create multimodal prompt with media files
            prompt_parts = []

            # Add media files first
            media_loaded = 0
            media_failed = 0
            for uri in file_uris[: settings.gemini_max_media_files]:  # Limit media for cost control
                try:
                    # Extract file name from URI if needed
                    if uri.startswith("https://generativelanguage.googleapis.com/v1beta/files/"):
                        file_name = uri.split("/files/")[-1]
                    else:
                        file_name = uri

                    file = await self._retry(self._gemini_get_file, file_name)
                    prompt_parts.append(file)
                    media_loaded += 1
                    logger.debug("Loaded media file for summary generation", uri=uri, file_name=file_name)
                except Exception as e:
                    media_failed += 1
                    logger.warning("Failed to load media file for summary generation", uri=uri, error=str(e))

            logger.info(
                "Media loading completed for multimodal summary",
                post_id=post.post_id,
                media_loaded=media_loaded,
                media_failed=media_failed,
                total_requested=len(file_uris[: settings.gemini_max_media_files]),
            )

            # Add the summary generation prompt
            prompt_parts.append("""Generate the three summaries in this exact format:

SHORT_TITLE: [3-5 word identifier]
TITLE: [One sentence summary]
DESCRIPTION: [One paragraph description]""")

            # Generate response with multimodal content
            multi_timeout = getattr(settings, "gemini_multimodal_timeout_seconds", None) or settings.gemini_timeout_seconds
            response = await self._retry(
                self._gemini_generate_content,
                model,
                prompt_parts,
                timeout=multi_timeout,
            )

            logger.debug(
                "Multimodal summary generation completed",
                post_id=post.post_id,
                response_length=len(response.text),
                media_used=media_loaded,
            )

            # Parse the structured response
            return self._parse_summary_response(response.text, post)

        except Exception as e:
            logger.warning(
                "Multimodal summary generation failed, using fallback",
                post_id=post.post_id,
                error=str(e),
                media_file_count=len(file_uris),
            )
            return self._generate_fallback_summaries(post)

    def _parse_summary_response(self, response_text: str, post: Post) -> Tuple[str, str, str]:
        """Parse the structured summary response from Gemini."""
        logger.debug("Parsing summary response", post_id=post.post_id, response_length=len(response_text))

        try:
            lines = response_text.strip().split("\n")

            short_title = ""
            title = ""
            description = ""

            for line in lines:
                line = line.strip()
                if line.startswith("SHORT_TITLE:"):
                    short_title = line.replace("SHORT_TITLE:", "").strip()
                elif line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                elif line.startswith("DESCRIPTION:"):
                    description = line.replace("DESCRIPTION:", "").strip()
                elif not short_title and not title and not description:
                    # If no structured format, treat first line as short title
                    short_title = line[:100]  # Cap at 100 chars

            # Ensure we have all three summaries
            parsing_warnings = []
            if not short_title:
                parsing_warnings.append("short_title not found in response")
                short_title = self._extract_short_title_from_content(post.content)
            if not title:
                parsing_warnings.append("title not found in response")
                title = self._extract_title_from_content(post.content)
            if not description:
                parsing_warnings.append("description not found in response")
                description = self._generate_fallback_description(post)

            # Log parsing warnings
            if parsing_warnings:
                logger.warning(
                    "Summary response parsing issues, used fallbacks",
                    post_id=post.post_id,
                    issues=parsing_warnings,
                    raw_response_sample=response_text[:200] + "..." if len(response_text) > 200 else response_text,
                )

            # Validate lengths
            short_title = short_title[:100]  # Limit to database column size
            title = title[:500]  # Limit to database column size

            logger.debug(
                "Summary parsing completed",
                post_id=post.post_id,
                short_title_length=len(short_title),
                title_length=len(title),
                description_length=len(description),
                had_parsing_issues=bool(parsing_warnings),
            )

            return short_title, title, description

        except Exception as e:
            logger.warning(
                "Failed to parse summary response, using complete fallbacks",
                post_id=post.post_id,
                error=str(e),
                raw_response_sample=response_text[:200] + "..." if len(response_text) > 200 else response_text,
            )
            return self._generate_fallback_summaries(post)

    def _generate_fallback_summaries(self, post: Post) -> Tuple[str, str, str]:
        """Generate basic fallback summaries when AI generation fails. Always returns valid non-empty strings."""
        logger.debug("Generating fallback summaries", post_id=post.post_id)

        short_title = self._extract_short_title_from_content(post.content)
        title = self._extract_title_from_content(post.content)
        description = self._generate_fallback_description(post)

        # Final validation to ensure non-empty strings
        if not short_title:
            short_title = "Content Analysis"
        if not title:
            title = "Social media content analysis summary"
        if not description:
            description = "Automated analysis of social media content for AI-generated patterns and authenticity assessment."

        logger.debug(
            "Fallback summaries generated",
            post_id=post.post_id,
            short_title=short_title,
            title_length=len(title),
            description_length=len(description),
        )

        return short_title, title, description

    def _generate_fallback_description(self, post: Post) -> str:
        """Generate a fallback description with detection details."""
        verdict_text = {
            "ai_slop": "appears to be AI-generated content",
            "human_content": "appears to be human-created content",
            "uncertain": "has uncertain authenticity",
        }.get(post.verdict, f"has verdict: {post.verdict}")

        description = f"Analysis of social media post by {post.author or 'Unknown'}. Content {verdict_text} with {(post.confidence * 100):.1f}% confidence."

        if post.explanation:
            description += f" {post.explanation}"
        else:
            description += " Detailed analysis includes text patterns, structural elements, and content authenticity indicators."

        return description

    def _extract_short_title_from_content(self, content: str) -> str:
        """Extract a short title from post content. Always returns non-empty string."""
        if not content or not content.strip():
            return "Content Analysis"

        # Take first few words, up to 5 words or 100 characters
        words = content.strip().split()[:5]
        short_title = " ".join(words)

        # Ensure we have something
        if not short_title:
            return "Content Analysis"

        # Clean up and truncate
        short_title = short_title.replace("\n", " ").replace("\t", " ")
        return short_title[:100] if len(short_title) <= 100 else short_title[:97] + "..."

    def _extract_title_from_content(self, content: str) -> str:
        """Extract a title from post content. Always returns non-empty string."""
        if not content or not content.strip():
            return "Social media content analysis summary"

        content = content.strip()

        # Take first sentence or first 500 characters
        sentences = content.split(". ")
        if sentences and sentences[0]:
            title = sentences[0].strip()
            if not title.endswith(".") and len(sentences) > 1:
                title += "."
        else:
            title = content[:500]

        # Ensure we have something
        if not title:
            return "Social media content analysis summary"

        # Clean up
        title = title.replace("\n", " ").replace("\t", " ")
        return title[:500] if len(title) <= 500 else title[:497] + "..."

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

        return "\n".join(summary_parts) if summary_parts else "No detailed detection results available"

    async def _get_post_gemini_file_uris(self, post_id: str, db: AsyncSession) -> List[str]:
        """Get pre-uploaded Gemini file URIs from post media table."""
        result = await db.execute(
            select(PostMedia.gemini_file_uri).where(PostMedia.post_id == post_id).where(PostMedia.gemini_file_uri.isnot(None))
        )
        return [uri for (uri,) in result.fetchall() if uri]

    # --- Utility methods for API calls with retry and concurrency ---

    async def _with_limit_and_timeout(self, func, *args, timeout: Optional[float] = None, **kwargs):
        """Run a blocking func in a thread with concurrency + timeout."""
        effective_timeout = timeout if timeout is not None else settings.gemini_timeout_seconds
        async with self._sem:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError as e:
                raise asyncio.TimeoutError(f"Gemini call timed out after {effective_timeout:.0f}s") from e

    async def _retry(self, coro_fn, *args, **kwargs):
        """Retry logic for Gemini API calls."""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.gemini_retry_max_attempts),
            wait=wait_exponential(multiplier=settings.gemini_retry_backoff_base, min=0.5, max=8),
            reraise=True,
        ):
            with attempt:
                return await coro_fn(*args, **kwargs)

    async def _gemini_generate_content(self, model, content, *, timeout: Optional[float] = None):
        """Generate content with Gemini model."""
        return await self._with_limit_and_timeout(model.generate_content, content, timeout=timeout)

    async def _gemini_get_file(self, file_name: str):
        """Get file from Gemini API."""
        return await self._with_limit_and_timeout(genai.get_file, file_name)


# Module-level singleton for injection in routes
post_summary_service = PostSummaryService.get_instance()
