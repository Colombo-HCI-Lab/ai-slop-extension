"""
Utility functions for video detection and testing.
"""

import logging
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def create_test_video(output_path: Path, duration_seconds: int = 5, fps: int = 20, resolution: Tuple[int, int] = (640, 480)) -> bool:
    """
    Create a simple test video with moving shapes for testing.

    Args:
        output_path: Path to save the video
        duration_seconds: Video duration in seconds
        fps: Frames per second
        resolution: Video resolution (width, height)

    Returns:
        True if video creation was successful, False otherwise
    """
    output_path = Path(output_path)
    width, height = resolution
    total_frames = duration_seconds * fps

    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, resolution)

        if not out.isOpened():
            logger.error(f"Failed to open video writer for {output_path}")
            return False

        logger.info(f"Creating test video with {total_frames} frames at {fps} fps...")

        for i in range(total_frames):
            # Create frame with black background
            frame = np.zeros((height, width, 3), dtype=np.uint8)

            # Moving circle (green)
            center_x = int(width // 2 + width // 4 * np.sin(i * 0.1))
            center_y = int(height // 2 + height // 4 * np.cos(i * 0.1))
            cv2.circle(frame, (center_x, center_y), 50, (0, 255, 0), -1)

            # Moving rectangle (blue)
            rect_x = int(100 + 50 * np.sin(i * 0.05))
            rect_y = int(100 + 50 * np.cos(i * 0.05))
            cv2.rectangle(frame, (rect_x, rect_y), (rect_x + 100, rect_y + 80), (255, 0, 0), -1)

            # Add some random noise for texture
            if i % 10 == 0:  # Every 10 frames
                noise = np.random.randint(0, 50, (height // 4, width // 4, 3), dtype=np.uint8)
                frame[height // 4 : height // 2, width // 4 : width // 2] += noise

            # Frame counter
            cv2.putText(frame, f"Frame {i:03d}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Duration indicator
            time_text = f"Time: {i / fps:.1f}s"
            cv2.putText(frame, time_text, (50, height - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            out.write(frame)

        out.release()
        logger.info(f"✓ Test video created successfully: {output_path}")
        logger.info(f"  Duration: {duration_seconds}s, Resolution: {width}x{height}, FPS: {fps}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to create test video: {e}")
        if "out" in locals():
            out.release()
        return False


def validate_video_file(video_path: Path) -> bool:
    """
    Validate if a video file can be opened and read.

    Args:
        video_path: Path to video file

    Returns:
        True if video is valid and readable
    """
    if not video_path.exists():
        logger.error(f"Video file does not exist: {video_path}")
        return False

    if not video_path.is_file():
        logger.error(f"Path is not a file: {video_path}")
        return False

    # Check file extension
    valid_extensions = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv", ".wmv"}
    if video_path.suffix.lower() not in valid_extensions:
        logger.warning(f"Unusual video extension: {video_path.suffix}")

    # Try to open with OpenCV
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Cannot open video file with OpenCV: {video_path}")
            return False

        # Check if we can read at least one frame
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            logger.error(f"Cannot read frames from video: {video_path}")
            return False

        logger.info(f"Video file validation passed: {video_path}")
        return True

    except Exception as e:
        logger.error(f"Error validating video file {video_path}: {e}")
        return False


def setup_logging(level: str = "INFO") -> None:
    """
    Setup logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_video_stats(video_path: Path) -> dict:
    """
    Get comprehensive video statistics.

    Args:
        video_path: Path to video file

    Returns:
        Dictionary with video statistics
    """
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    stats = {
        "filename": video_path.name,
        "path": str(video_path),
        "file_size_mb": video_path.stat().st_size / (1024 * 1024),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "codec": cap.get(cv2.CAP_PROP_FOURCC),
    }

    # Calculate duration
    if stats["fps"] > 0:
        stats["duration_seconds"] = stats["frame_count"] / stats["fps"]
        stats["duration_formatted"] = f"{stats['duration_seconds']:.1f}s"
    else:
        stats["duration_seconds"] = 0
        stats["duration_formatted"] = "Unknown"

    # Format resolution
    stats["resolution"] = f"{stats['width']}x{stats['height']}"

    cap.release()
    return stats
