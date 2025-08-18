"""
Configuration settings for ClipBased detection.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Default model configurations
DEFAULT_MODELS = {
    "openclip_vit_l14": {
        "arch": "openclip",
        "model_name": "ViT-L-14",
        "pretrained": "laion2b_s32b_b82k",
        "num_classes": 1,
        "normalize_features": True,
        "use_next_to_last": False,
    },
    "openclip_vit_b32": {
        "arch": "openclip",
        "model_name": "ViT-B-32",
        "pretrained": "laion2b_s34b_b79k",
        "num_classes": 1,
        "normalize_features": True,
        "use_next_to_last": False,
    },
    "openclip_eva02_l14": {
        "arch": "openclip",
        "model_name": "EVA02-L-14",
        "pretrained": "merged2b_s4b_b131k",
        "num_classes": 1,
        "normalize_features": True,
        "use_next_to_last": False,
    },
}


# Environment-based configuration
class ClipBasedConfig:
    def __init__(self):
        # Use local models directory by default
        package_dir = Path(__file__).parent
        self.model_path = os.getenv("CLIPBASED_MODEL_PATH", str(package_dir / "weights"))
        self.default_model = os.getenv("CLIPBASED_DEFAULT_MODEL", "openclip_vit_l14")
        self.batch_size = int(os.getenv("CLIPBASED_BATCH_SIZE", "16"))
        self.threshold = float(os.getenv("CLIPBASED_THRESHOLD", "0.0"))  # LLR > 0 indicates synthetic
        self.device = os.getenv("CLIPBASED_DEVICE", "auto")
        self.precision = os.getenv("CLIPBASED_PRECISION", "float32")

        # Image preprocessing settings
        self.image_size = int(os.getenv("CLIPBASED_IMAGE_SIZE", "224"))
        self.crop_size = int(os.getenv("CLIPBASED_CROP_SIZE", "224"))
        self.normalize_mean = [0.485, 0.456, 0.406]  # ImageNet normalization
        self.normalize_std = [0.229, 0.224, 0.225]

        # Performance settings
        self.max_image_size = int(os.getenv("MAX_IMAGE_SIZE", "10485760"))  # 10MB
        self.max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "10"))

        # Ensure model path exists
        Path(self.model_path).mkdir(parents=True, exist_ok=True)

    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get configuration for a specific model."""
        model_name = model_name or self.default_model
        if model_name not in DEFAULT_MODELS:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(DEFAULT_MODELS.keys())}")
        return DEFAULT_MODELS[model_name].copy()

    def get_available_models(self) -> list:
        """Get list of available model names."""
        return list(DEFAULT_MODELS.keys())


# Global config instance
config = ClipBasedConfig()
