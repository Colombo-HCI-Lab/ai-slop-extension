"""
SlowFast model wrapper for AI-generated vs real video classification.
"""

import logging
from pathlib import Path
from typing import Dict, List, Union, Optional

import torch
import torch.nn.functional as F

try:
    import pytorchvideo.models.hub as model_hub
except ImportError as e:
    logging.error(f"Error importing PyTorchVideo: {e}")
    logging.error("Please ensure PyTorchVideo is installed")
    raise

logger = logging.getLogger(__name__)


class AIVideoDetector:
    """SlowFast model wrapper for AI-generated vs real video classification"""

    def __init__(self, model_name: str = "slowfast_r50", device: Optional[str] = None, ai_threshold: float = 0.5):
        """
        Initialize AI video detector.

        Args:
            model_name: Name of the SlowFast model to load
            device: Device to run inference on (auto-detect if None)
            ai_threshold: Threshold for classifying as AI-generated (0.0-1.0)
        """
        self.model_name = model_name
        # Handle device auto-detection
        if device == "auto" or device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.ai_threshold = ai_threshold
        self.model = None

        logger.info(f"Initializing AIVideoDetector with model: {model_name}, device: {self.device}, threshold: {ai_threshold}")

        # Load pretrained model
        self._load_model()

    def _load_model(self):
        """Load the SlowFast model."""
        logger.info(f"Loading {self.model_name} model...")

        try:
            # Try to load from local weights first, fallback to hub
            model_weights_path = Path(__file__).parent / "models" / f"{self.model_name}_pretrained.pth"

            # Auto-download models if missing
            if not model_weights_path.exists() and self.model_name in ["slowfast_r50", "slowfast_r101"]:
                logger.info(f"Model weights not found at {model_weights_path}")
                logger.info("Downloading model from PyTorchVideo hub...")

                # Ensure models directory exists
                model_weights_path.parent.mkdir(exist_ok=True)

                # Download and save model
                if self.model_name == "slowfast_r50":
                    model = model_hub.slowfast_r50(pretrained=True)
                else:  # slowfast_r101
                    model = model_hub.slowfast_r101(pretrained=True)

                # Save model weights
                torch.save(model.state_dict(), model_weights_path)
                logger.info(f"Model saved to {model_weights_path} ({model_weights_path.stat().st_size / 1024 / 1024:.1f} MB)")

            # Map model names to hub functions
            model_mapping = {
                "slowfast_r50": lambda: model_hub.slowfast_r50(pretrained=not model_weights_path.exists()),
                "slowfast_r101": lambda: model_hub.slowfast_r101(pretrained=not model_weights_path.exists()),
                "x3d_m": lambda: model_hub.x3d_m(pretrained=True),
                "x3d_l": lambda: model_hub.x3d_l(pretrained=True),
            }

            if self.model_name not in model_mapping:
                raise ValueError(f"Unsupported model: {self.model_name}. Available: {list(model_mapping.keys())}")

            self.model = model_mapping[self.model_name]()

            # Load local weights if available
            if model_weights_path.exists() and self.model_name in ["slowfast_r50", "slowfast_r101"]:
                logger.info(f"Loading model from local weights: {model_weights_path}")
                state_dict = torch.load(model_weights_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
            else:
                logger.info("Using pretrained weights from PyTorchVideo hub")

            self.model = self.model.to(self.device)
            self.model.eval()
            logger.info(f"Successfully loaded {self.model_name} on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise

    def predict(self, video_input: Union[torch.Tensor, List[torch.Tensor]]) -> Dict:
        """
        Run inference on video input for AI vs real classification.

        Args:
            video_input: SlowFast input tensors [slow_pathway, fast_pathway]

        Returns:
            Dictionary containing detection results
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        try:
            with torch.no_grad():
                # Move input to device
                if isinstance(video_input, list):
                    video_input = [x.to(self.device) for x in video_input]
                else:
                    video_input = video_input.to(self.device)

                # Forward pass with timing
                start_time = torch.cuda.Event(enable_timing=True) if self.device == "cuda" else None
                end_time = torch.cuda.Event(enable_timing=True) if self.device == "cuda" else None

                if start_time:
                    start_time.record()

                outputs = self.model(video_input)

                if end_time:
                    end_time.record()
                    torch.cuda.synchronize()
                    inference_time = start_time.elapsed_time(end_time) / 1000.0
                else:
                    inference_time = 0.0

                # Apply softmax to get probabilities
                probs = F.softmax(outputs, dim=1)

                # Get the highest confidence prediction
                max_prob, max_idx = torch.max(probs, dim=1)
                confidence = float(max_prob[0])

                # Simple heuristic for AI detection
                # This is a placeholder - in practice you'd train a specific model
                # for AI-generated vs real video classification

                # Basic classification logic
                is_ai_generated = confidence < self.ai_threshold

                # If confidence is very high, might indicate overly perfect/synthetic content
                if confidence > 0.95:
                    is_ai_generated = True

                ai_probability = 1.0 - confidence if is_ai_generated else confidence - 0.5

                return {
                    "is_ai_generated": is_ai_generated,
                    "confidence": confidence,
                    "ai_probability": max(0.0, min(1.0, ai_probability)),
                    "model_confidence": confidence,
                    "threshold_used": self.ai_threshold,
                    "raw_prediction_index": int(max_idx[0]),
                    "model_used": self.model_name,
                    "processing_time": inference_time,
                }

        except Exception as e:
            logger.error(f"AI detection failed: {e}")
            raise

    def get_model_info(self) -> Dict:
        """Get information about the current model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "threshold": self.ai_threshold,
            "pytorch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "loaded": self.model is not None,
            "classification_type": "ai_vs_real",
        }

    def set_threshold(self, threshold: float):
        """Update the AI detection threshold."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self.ai_threshold = threshold
        logger.info(f"AI threshold updated to {threshold}")

    def cleanup(self):
        """Clean up model resources."""
        if self.model is not None:
            del self.model
            self.model = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            logger.info(f"Cleaned up AI video detector: {self.model_name}")
