"""ML: Clip-based image detection wrapper.

This module provides a stable import path for clip-based image detection under
`ml.clipbased`. It re-exports the public API from the existing implementation
in `clipbased_detection` to avoid a large, risky move. When ready, the
implementation can be physically moved under this package without changing
import sites again.
"""

from .impl import ClipBasedImageDetector  # public API surface

__all__ = ["ClipBasedImageDetector"]
