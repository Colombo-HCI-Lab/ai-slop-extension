"""Text content AI detection service."""

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Post
from schemas.text_detection import DetectRequest, DetectResponse

logger = logging.getLogger(__name__)


class TextDetectionService:
    """Service for detecting AI-generated text content."""

    def __init__(self):
        """Initialize the text detection service."""
        self.request_counter = 0
        self.ai_indicators = [
            "it is important to note",
            "in conclusion",
            "moreover",
            "furthermore",
            "it should be noted",
            "delve into",
            "tapestry",
            "navigate",
            "landscape",
            "realm",
            "embark",
            "journey",
            "pivotal",
            "paramount",
            "unprecedented",
            "revolutionize",
            "cutting-edge",
            "seamlessly",
            "robust solution",
            "leveraging",
        ]

    async def detect(
        self,
        request: DetectRequest,
        db: AsyncSession,
        use_cache: bool = True,
    ) -> DetectResponse:
        """
        Detect if text content is AI-generated.

        Args:
            request: Detection request with content and post ID
            db: Database session
            use_cache: Whether to use cached results

        Returns:
            Detection response with verdict and confidence
        """
        self.request_counter += 1

        # Check cache if enabled
        if use_cache:
            cached_result = await self._get_cached_result(request.post_id, db)
            if cached_result:
                logger.info(f"Returning cached result for post {request.post_id}")
                return self._create_response_from_post(cached_result, from_cache=True)

        # Perform detection
        verdict, confidence, explanation, ai_probability, analysis_confidence = self._analyze_content(request.content)

        # Save to database
        post = await self._save_to_database(request, verdict, confidence, explanation, ai_probability, analysis_confidence, db)

        return self._create_response_from_post(post, from_cache=False)

    async def _get_cached_result(self, post_id: str, db: AsyncSession) -> Optional[Post]:
        """Get cached result from database."""
        result = await db.execute(select(Post).where(Post.post_id == post_id))
        return result.scalar_one_or_none()

    def _analyze_content(self, content: str) -> tuple[str, float, str, float, float]:
        """
        Analyze content for AI-generated patterns.

        Returns:
            Tuple of (verdict, confidence, explanation, ai_probability, analysis_confidence)
        """
        # For testing mode, use random detection
        if self._is_testing_mode():
            return self._random_detection(content)

        # Real detection logic
        content_lower = content.lower()
        matched_indicators = [indicator for indicator in self.ai_indicators if indicator in content_lower]

        indicator_score = len(matched_indicators)
        
        # Legacy confidence calculation for backward compatibility
        legacy_confidence = min(0.95, 0.2 + indicator_score * 0.15)

        # New AI probability calculation (0.0 = definitely human, 1.0 = definitely AI)
        # Base probability starts at 0.1 (slight chance it could be AI)
        # Each indicator adds 0.08 probability
        ai_probability = min(0.95, 0.1 + indicator_score * 0.08)
        
        # Analysis confidence (how confident we are in our assessment)
        # Higher confidence with more indicators (either way)
        # Base confidence of 0.3, increases with indicators found
        analysis_confidence = min(0.95, 0.3 + indicator_score * 0.1)
        
        # If no indicators, we're reasonably confident it's human content
        if indicator_score == 0:
            ai_probability = 0.05  # Very low chance of being AI
            analysis_confidence = 0.75  # Reasonably confident in human assessment

        if indicator_score >= 3:
            verdict = "ai_slop"
        elif indicator_score == 0:
            verdict = "human_content"
        else:
            verdict = "uncertain"

        explanation = (
            f"Detected {indicator_score} AI-typical phrase(s): "
            f"{', '.join(matched_indicators[:3])}"
            f"{'...' if len(matched_indicators) > 3 else ''}"
            if indicator_score > 0
            else "No AI-typical patterns detected"
        )

        logger.debug(f"Analysis complete - Verdict: {verdict}, Legacy Confidence: {legacy_confidence:.2%}, AI Probability: {ai_probability:.2%}, Analysis Confidence: {analysis_confidence:.2%}, Indicators: {indicator_score}")

        return verdict, legacy_confidence, explanation, ai_probability, analysis_confidence

    def _random_detection(self, content: str) -> tuple[str, float, str, float, float]:
        """Random detection for testing."""
        import random

        is_ai_slop = random.random() > 0.5
        
        # Legacy confidence for backward compatibility
        legacy_confidence = (
            0.65 + random.random() * 0.35  # 65-100% for AI slop
            if is_ai_slop
            else 0.15 + random.random() * 0.35  # 15-50% for human content
        )

        # AI probability (0.0 = human, 1.0 = AI)
        ai_probability = (
            0.7 + random.random() * 0.25  # 70-95% probability for AI content
            if is_ai_slop
            else 0.05 + random.random() * 0.25  # 5-30% probability for human content
        )
        
        # Analysis confidence (how sure we are)
        analysis_confidence = 0.6 + random.random() * 0.35  # 60-95% confidence

        verdict = "ai_slop" if is_ai_slop else "human_content"

        ai_explanations = [
            "Content exhibits repetitive phrasing and generic language patterns typical of AI generation",
            "Detected multiple AI-typical markers including formulaic expressions and lack of personal voice",
            "Writing style shows signs of automated generation with predictable sentence structures",
            "Content lacks authentic human experiences and uses overly formal language patterns",
        ]

        human_explanations = [
            "Content shows natural language variations and personal voice",
            "Writing exhibits genuine human experiences and emotional authenticity",
            "Text contains colloquialisms and natural conversational flow",
            "Content displays unique perspective and spontaneous expression",
        ]

        explanation = random.choice(ai_explanations) if is_ai_slop else random.choice(human_explanations)

        return verdict, legacy_confidence, explanation, ai_probability, analysis_confidence

    def _is_testing_mode(self) -> bool:
        """Check if running in testing mode."""
        # You can configure this via environment variable
        import os

        return os.getenv("DETECTION_MODE", "real").lower() == "testing"

    async def _save_to_database(
        self,
        request: DetectRequest,
        verdict: str,
        confidence: float,
        explanation: str,
        ai_probability: float,
        analysis_confidence: float,
        db: AsyncSession,
    ) -> Post:
        """Save detection result to database."""
        # Check if post already exists
        existing = await self._get_cached_result(request.post_id, db)

        if existing:
            # Update existing post
            existing.content = request.content
            existing.author = request.author
            existing.verdict = verdict
            existing.confidence = confidence
            existing.explanation = explanation
            existing.text_ai_probability = ai_probability
            existing.text_confidence = analysis_confidence
            existing.updated_at = datetime.utcnow()
            await db.commit()
            return existing

        # Create new post
        post = Post(
            id=str(uuid.uuid4()),
            post_id=request.post_id,
            content=request.content,
            author=request.author,
            verdict=verdict,
            confidence=confidence,
            explanation=explanation,
            text_ai_probability=ai_probability,
            text_confidence=analysis_confidence,
            post_metadata=request.metadata,
        )

        db.add(post)
        await db.commit()
        await db.refresh(post)

        return post

    def _create_response_from_post(self, post: Post, from_cache: bool = False) -> DetectResponse:
        """Create detection response from post model."""
        return DetectResponse(
            post_id=post.post_id,
            verdict=post.verdict,
            confidence=post.confidence,
            explanation=post.explanation,
            timestamp=post.updated_at.isoformat(),
            text_ai_probability=post.text_ai_probability,
            text_confidence=post.text_confidence,
            text_analysis={"verdict": post.verdict, "confidence": post.confidence, "explanation": post.explanation},
            image_analysis=[],
            video_analysis=[],
            debug_info={
                "mode": "cached_result" if from_cache else "real_detection",
                "request_number": self.request_counter,
                "from_cache": from_cache,
            },
        )

    async def get_cache_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get cache statistics."""
        result = await db.execute(select(Post))
        posts = result.scalars().all()

        total_posts = len(posts)
        ai_slop_count = sum(1 for p in posts if p.verdict == "ai_slop")
        human_count = sum(1 for p in posts if p.verdict == "human_content")
        uncertain_count = sum(1 for p in posts if p.verdict == "uncertain")

        return {
            "total_cached": total_posts,
            "ai_slop": ai_slop_count,
            "human_content": human_count,
            "uncertain": uncertain_count,
            "cache_hit_rate": "N/A",  # Would need to track this separately
            "last_updated": datetime.utcnow().isoformat(),
        }
