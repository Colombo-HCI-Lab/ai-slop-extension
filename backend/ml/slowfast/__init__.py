"""ML: SlowFast video detection wrapper.

This module provides a stable import path for SlowFast-based video detection
under `ml.slowfast`. It re-exports the public API from the existing
implementation in `slowfast_detection` to minimize disruption. The underlying
package can be moved later without changing import sites again.
"""

from .impl import AIVideoDetector, VideoPreprocessor  # public API surface

__all__ = ["AIVideoDetector", "VideoPreprocessor"]
