"""
ClipBased AI-generated image detection implementation.
"""

import logging
import time
from pathlib import Path
from typing import Union, List, Dict, Any, Optional

import numpy as np
import torch
from PIL import Image

from .config import config
from .models import ClipBasedDetector
from .preprocessing import ImagePreprocessor
from .utils import download_image_from_url

logger = logging.getLogger(__name__)


class ClipBasedImageDetector:
    """
    Main class for ClipBased AI-generated image detection.

    Provides a high-level interface for loading models and detecting synthetic images.
    """

    def __init__(self, model_name: str = None, device: str = "auto", weights_path: Optional[str] = None):
        """
        Initialize the ClipBased detector.

        Args:
            model_name: Name of the model to use
            device: Device to run inference on ("auto", "cuda", "cpu")
            weights_path: Path to pre-trained weights (optional)
        """
        self.model_name = model_name or config.default_model
        self.device = self._get_device(device)
        self.weights_path = weights_path

        # Initialize components
        self.model = None
        self.preprocessor = None
        self.is_loaded = False

        # Performance tracking
        self.inference_times = []

        logger.info(f"Initialized ClipBased detector with model: {self.model_name}")

    def _get_device(self, device: str) -> torch.device:
        """Determine the appropriate device for inference."""
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

        return torch.device(device)

    def load_model(self) -> None:
        """Load the ClipBased model and preprocessor."""
        try:
            # Get model configuration
            model_config = config.get_model_config(self.model_name)

            # Initialize model
            self.model = ClipBasedDetector(model_config)

            # Load pre-trained weights if available
            if self.weights_path and Path(self.weights_path).exists():
                self.model.load_weights(self.weights_path)
            else:
                logger.warning(f"No weights found at {self.weights_path}, using random initialization")

            # Move model to device and set to evaluation mode
            self.model = self.model.to(self.device)
            self.model.eval()

            # Initialize preprocessor
            self.preprocessor = ImagePreprocessor(
                image_size=config.image_size,
                crop_size=config.crop_size,
                normalize_mean=config.normalize_mean,
                normalize_std=config.normalize_std,
            )

            self.is_loaded = True
            logger.info(f"Successfully loaded ClipBased model on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load ClipBased model: {e}")
            raise

    def detect_image(self, image: Union[str, Image.Image, np.ndarray], threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Detect if an image is AI-generated.

        Args:
            image: Input image (file path, PIL Image, or numpy array)
            threshold: Detection threshold (uses config default if None)

        Returns:
            Dictionary with detection results
        """
        if not self.is_loaded:
            self.load_model()

        threshold = threshold if threshold is not None else config.threshold
        start_time = time.time()

        try:
            # Preprocess image
            preprocessed = self.preprocessor.preprocess_image(image)
            batch = preprocessed.unsqueeze(0).to(self.device)

            # Run inference
            with torch.no_grad():
                llr_score = self.model.get_llr_score(batch)
                probability = self.model.predict_proba(batch)
                prediction = self.model.predict(batch, threshold)

            # Extract values from tensors
            llr_value = llr_score.item()
            prob_value = probability.item()
            is_synthetic = prediction.item() == 1

            inference_time = time.time() - start_time
            self.inference_times.append(inference_time)

            # Get image metadata
            if isinstance(image, str):
                image_info = self.preprocessor.get_image_info(image)
            else:
                image_info = {"size": "unknown", "format": "unknown"}

            return {
                "is_ai_generated": is_synthetic,
                "confidence": abs(llr_value),  # Absolute value for confidence
                "llr_score": llr_value,
                "probability": prob_value,
                "threshold": threshold,
                "model_used": self.model_name,
                "processing_time": inference_time,
                "metadata": {
                    "image_size": image_info.get("size", "unknown"),
                    "format": image_info.get("format", "unknown"),
                    "device": str(self.device),
                    "model_version": "v1.0",
                },
            }

        except Exception as e:
            logger.error(f"Detection failed for image: {e}")
            raise

    def detect_batch(
        self, images: List[Union[str, Image.Image, np.ndarray]], threshold: Optional[float] = None, batch_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect AI-generated content in a batch of images.

        Args:
            images: List of input images
            threshold: Detection threshold
            batch_size: Batch size for processing (uses config default if None)

        Returns:
            List of detection results for each image
        """
        if not self.is_loaded:
            self.load_model()

        threshold = threshold if threshold is not None else config.threshold
        batch_size = batch_size if batch_size is not None else config.batch_size

        results = []

        # Process images in batches
        for i in range(0, len(images), batch_size):
            batch_images = images[i : i + batch_size]

            try:
                # Preprocess batch
                batch_tensor = self.preprocessor.preprocess_batch(batch_images)
                batch_tensor = batch_tensor.to(self.device)

                start_time = time.time()

                # Run inference
                with torch.no_grad():
                    llr_scores = self.model.get_llr_score(batch_tensor)
                    probabilities = self.model.predict_proba(batch_tensor)
                    predictions = self.model.predict(batch_tensor, threshold)

                inference_time = time.time() - start_time

                # Process results for each image in batch
                for j, (llr, prob, pred) in enumerate(zip(llr_scores, probabilities, predictions)):
                    image_idx = i + j

                    if image_idx < len(images):
                        image = images[image_idx]

                        # Get image metadata
                        if isinstance(image, str):
                            image_info = self.preprocessor.get_image_info(image)
                        else:
                            image_info = {"size": "unknown", "format": "unknown"}

                        result = {
                            "is_ai_generated": pred.item() == 1,
                            "confidence": abs(llr.item()),
                            "llr_score": llr.item(),
                            "probability": prob.item(),
                            "threshold": threshold,
                            "model_used": self.model_name,
                            "processing_time": inference_time / len(batch_images),
                            "metadata": {
                                "image_size": image_info.get("size", "unknown"),
                                "format": image_info.get("format", "unknown"),
                                "device": str(self.device),
                                "model_version": "v1.0",
                                "batch_index": image_idx,
                            },
                        }
                        results.append(result)

            except Exception as e:
                logger.error(f"Batch processing failed for batch {i // batch_size}: {e}")
                # Add error results for failed batch
                for j in range(len(batch_images)):
                    results.append({"is_ai_generated": False, "confidence": 0.0, "error": str(e), "model_used": self.model_name})

        return results

    def detect_from_url(self, url: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Detect AI-generated content from image URL.

        Args:
            url: URL of the image to analyze
            threshold: Detection threshold

        Returns:
            Detection results dictionary
        """
        try:
            # Download image from URL
            image = download_image_from_url(url)

            # Run detection
            result = self.detect_image(image, threshold)

            # Add URL to metadata
            result["metadata"]["source_url"] = url

            return result

        except Exception as e:
            logger.error(f"URL detection failed for {url}: {e}")
            raise

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for the detector."""
        if not self.inference_times:
            return {"message": "No inference times recorded"}

        times = np.array(self.inference_times)
        return {
            "total_inferences": len(times),
            "mean_time": float(np.mean(times)),
            "median_time": float(np.median(times)),
            "min_time": float(np.min(times)),
            "max_time": float(np.max(times)),
            "std_time": float(np.std(times)),
        }

    def cleanup(self) -> None:
        """Clean up model resources."""
        if self.model is not None:
            del self.model
            self.model = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self.is_loaded = False
        logger.info("ClipBased detector resources cleaned up")


def create_detector(model_name: str = None, device: str = "auto", weights_path: Optional[str] = None) -> ClipBasedImageDetector:
    """
    Factory function to create a ClipBased detector.

    Args:
        model_name: Name of the model to use
        device: Device for inference
        weights_path: Path to pre-trained weights

    Returns:
        Configured ClipBasedImageDetector instance
    """
    return ClipBasedImageDetector(model_name=model_name, device=device, weights_path=weights_path)
