"""
ClipBased AI-generated image detection integration.
Contains ClipBased framework components for synthetic image detection.
"""

__version__ = "0.1.0"


# Conditional imports to avoid dependency issues during basic testing
def _import_with_fallback():
    """Import main classes with graceful fallback."""
    try:
        from .detection import ClipBasedImageDetector, create_detector

        return ClipBasedImageDetector, create_detector
    except ImportError as e:
        import warnings

        warnings.warn(f"Could not import ClipBased detection classes: {e}")
        return None, None


ClipBasedImageDetector, create_detector = _import_with_fallback()

# Core exports for image detection
try:
    from . import models
    from . import utils
    from . import weights
except ImportError as e:
    import warnings

    warnings.warn(f"Could not import ClipBased components: {e}")
    models = None
    utils = None
    weights = None

__all__ = ["ClipBasedImageDetector", "create_detector", "models", "utils", "weights", "__version__"]
