"""
ClipBased model implementations based on the original repository.
"""

import logging
from typing import Dict, Any

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class OpenClipLinear(nn.Module):
    """
    OpenCLIP-based model for synthetic image detection.

    Based on the original implementation from ClipBased-SyntheticImageDetection.
    """

    def __init__(
        self,
        model_name: str = "ViT-L-14",
        pretrained: str = "laion2b_s32b_b82k",
        num_classes: int = 1,
        normalize_features: bool = True,
        use_next_to_last: bool = False,
    ):
        super().__init__()

        self.model_name = model_name
        self.pretrained = pretrained
        self.num_classes = num_classes
        self.normalize_features = normalize_features
        self.use_next_to_last = use_next_to_last

        # Import open_clip here to avoid dependency issues during package initialization
        try:
            import open_clip

            self.open_clip = open_clip
        except ImportError:
            raise ImportError("open_clip_torch is required for ClipBased detection. Install with: pip install open_clip_torch")

        # Load the CLIP model
        self._load_model()

    def _load_model(self):
        """Load the OpenCLIP model and set up the classification layer."""
        try:
            # Load pre-trained CLIP model
            model, _, preprocess = self.open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                device="cpu",  # Load on CPU first, then move to device
            )

            # Extract visual backbone
            self.backbone = model.visual

            # Freeze backbone parameters
            for param in self.backbone.parameters():
                param.requires_grad = False

            # Get feature dimension
            with torch.no_grad():
                dummy_input = torch.randn(1, 3, 224, 224)
                if hasattr(self.backbone, "forward_features"):
                    features = self.backbone.forward_features(dummy_input)
                else:
                    # Fallback for different CLIP implementations
                    features = self.backbone(dummy_input)
                feature_dim = features.shape[-1]

            # Create classification head
            self.classifier = nn.Linear(feature_dim, self.num_classes)

            # Initialize classifier weights
            nn.init.normal_(self.classifier.weight, std=0.01)
            if self.classifier.bias is not None:
                nn.init.constant_(self.classifier.bias, 0)

            logger.info(f"Loaded OpenCLIP model: {self.model_name} with {feature_dim} features")

        except Exception as e:
            logger.error(f"Failed to load OpenCLIP model {self.model_name}: {e}")
            raise

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract features from the CLIP backbone."""
        if hasattr(self.backbone, "forward_features"):
            features = self.backbone.forward_features(x)
        else:
            # Fallback for different CLIP implementations
            features = self.backbone(x)

        if self.normalize_features:
            features = nn.functional.normalize(features, p=2, dim=-1)

        return features

    def forward_head(self, features: torch.Tensor) -> torch.Tensor:
        """Apply classification head to features."""
        return self.classifier(features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Full forward pass through the model."""
        features = self.forward_features(x)
        logits = self.forward_head(features)
        return logits


class ClipBasedDetector(nn.Module):
    """
    Main ClipBased detector that wraps different model architectures.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__()

        self.config = config
        self.arch = config.get("arch", "openclip")

        if self.arch == "openclip":
            self.model = OpenClipLinear(
                model_name=config.get("model_name", "ViT-L-14"),
                pretrained=config.get("pretrained", "laion2b_s32b_b82k"),
                num_classes=config.get("num_classes", 1),
                normalize_features=config.get("normalize_features", True),
                use_next_to_last=config.get("use_next_to_last", False),
            )
        else:
            raise ValueError(f"Unsupported architecture: {self.arch}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through the detector."""
        return self.model(x)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Get probability predictions."""
        logits = self.forward(x)
        if self.config.get("num_classes", 1) == 1:
            # Binary classification with LLR score
            return torch.sigmoid(logits)
        else:
            # Multi-class classification
            return torch.softmax(logits, dim=-1)

    def predict(self, x: torch.Tensor, threshold: float = 0.0) -> torch.Tensor:
        """Get binary predictions based on threshold."""
        logits = self.forward(x)
        if self.config.get("num_classes", 1) == 1:
            # For LLR scoring: positive values indicate synthetic
            return (logits > threshold).int()
        else:
            # Multi-class: return class with highest probability
            return torch.argmax(logits, dim=-1)

    def get_llr_score(self, x: torch.Tensor) -> torch.Tensor:
        """Get Log-Likelihood Ratio score (raw logits)."""
        return self.forward(x)

    def load_weights(self, weight_path: str):
        """Load pre-trained weights."""
        try:
            state_dict = torch.load(weight_path, map_location="cpu")

            # Handle different state dict formats
            if "model" in state_dict:
                state_dict = state_dict["model"]
            elif "state_dict" in state_dict:
                state_dict = state_dict["state_dict"]

            # Load weights with proper key mapping
            model_state_dict = self.state_dict()
            filtered_state_dict = {}

            for k, v in state_dict.items():
                # Remove module prefix if present
                key = k.replace("module.", "")
                if key in model_state_dict:
                    filtered_state_dict[key] = v
                else:
                    logger.warning(f"Ignoring key {key} in checkpoint")

            self.load_state_dict(filtered_state_dict, strict=False)
            logger.info(f"Loaded weights from {weight_path}")

        except Exception as e:
            logger.error(f"Failed to load weights from {weight_path}: {e}")
            raise
