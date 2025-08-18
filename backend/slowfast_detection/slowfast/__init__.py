"""
SlowFast framework integration for video detection.
Contains essential SlowFast components for AI-generated video detection.
"""

__version__ = "0.1.0"

# Core exports for video detection
models = None
config = None
utils = None
datasets = None

try:
    from . import models
    from . import config
    from . import utils
    from . import datasets
except ImportError as e:
    import warnings

    warnings.warn(f"Could not import SlowFast components: {e}")

__all__ = ["models", "config", "utils", "datasets", "__version__"]
