"""Utility functions for extracting Facebook media IDs from URLs."""

import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

from utils.logging import get_logger

logger = get_logger(__name__)


def extract_facebook_media_id(url: str) -> Optional[str]:
    """
    Extract unique Facebook media ID from various Facebook media URL formats.

    Supports:
    - Image URLs: /photo/?fbid=MEDIA_ID&...
    - Video URLs: /videos/MEDIA_ID/ or /watch/?v=MEDIA_ID

    Args:
        url: Facebook media URL (can be relative or absolute)

    Returns:
        str: Extracted media ID if found, None otherwise

    Examples:
        >>> extract_facebook_media_id("/photo/?fbid=3156563787835105&set=g.1638417209555402")
        "3156563787835105"

        >>> extract_facebook_media_id("/videos/348422766084288/?idorvanity=1638417209555402")
        "348422766084288"

        >>> extract_facebook_media_id("https://www.facebook.com/photo/?fbid=1378895026734715&set=gm.24335126272791173")
        "1378895026734715"
    """
    if not url:
        return None

    try:
        # Handle both relative and absolute URLs
        if not url.startswith(("http://", "https://")):
            url = "https://facebook.com" + url

        parsed_url = urlparse(url)

        # For image URLs: extract fbid parameter
        if "/photo/" in parsed_url.path:
            query_params = parse_qs(parsed_url.query)
            fbid = query_params.get("fbid")
            if fbid and fbid[0]:
                logger.debug(f"Extracted image media ID: {fbid[0]} from {url}")
                return fbid[0]

        # For video URLs: extract from path pattern /videos/ID/
        video_path_match = re.search(r"/videos/(\d+)", parsed_url.path)
        if video_path_match:
            media_id = video_path_match.group(1)
            logger.debug(f"Extracted video media ID: {media_id} from {url}")
            return media_id

        # For watch URLs: extract v parameter
        if "/watch/" in parsed_url.path:
            query_params = parse_qs(parsed_url.query)
            video_id = query_params.get("v")
            if video_id and video_id[0]:
                logger.debug(f"Extracted watch video ID: {video_id[0]} from {url}")
                return video_id[0]

        # Try to extract any numeric ID from the path as fallback
        numeric_match = re.search(r"/(\d{10,})", parsed_url.path)
        if numeric_match:
            media_id = numeric_match.group(1)
            logger.debug(f"Extracted fallback media ID: {media_id} from {url}")
            return media_id

        logger.warning(f"Could not extract media ID from URL: {url}")
        return None

    except Exception as e:
        logger.error(f"Error extracting media ID from URL {url}: {str(e)}")
        return None


def generate_composite_media_id(post_id: str, media_url: str, media_type: str) -> str:
    """
    Generate a composite media ID that includes Facebook media ID if available.
    Falls back to a hash-based approach if Facebook ID cannot be extracted.

    Args:
        post_id: Facebook post ID
        media_url: Media URL
        media_type: Type of media ('image' or 'video')

    Returns:
        str: Composite media ID in format 'fbid_{facebook_id}' or 'hash_{hash}'
    """
    import hashlib

    # Try to extract Facebook media ID first
    fb_media_id = extract_facebook_media_id(media_url)

    if fb_media_id:
        # Use Facebook media ID with prefix to avoid collisions
        composite_id = f"fb_{fb_media_id}"
        logger.debug(f"Generated FB-based media ID: {composite_id}")
        return composite_id

    # Fallback: generate hash-based ID
    # Use post_id + media_url + media_type to ensure uniqueness
    content_to_hash = f"{post_id}|{media_url}|{media_type}"
    hash_value = hashlib.sha256(content_to_hash.encode()).hexdigest()[:16]
    composite_id = f"hash_{hash_value}"

    logger.debug(f"Generated hash-based media ID: {composite_id} for URL: {media_url}")
    return composite_id
