"""
SlowFast AI-generated video detection package.

This package provides video preprocessing, model inference, and utilities
for detecting AI-generated content in videos using SlowFast models.
"""

__version__ = "0.1.0"


# Conditional imports to avoid dependency issues during basic testing
def _import_with_fallback():
    """Import main classes with graceful fallback."""
    try:
        from .preprocessing import VideoPreprocessor
        from .detection import AIVideoDetector
        from .utils import create_test_video

        return VideoPreprocessor, AIVideoDetector, create_test_video
    except ImportError as e:
        import warnings

        warnings.warn(f"Could not import detection classes: {e}")
        return None, None, None


VideoPreprocessor, AIVideoDetector, create_test_video = _import_with_fallback()

__all__ = ["VideoPreprocessor", "AIVideoDetector", "create_test_video", "__version__"]
