"""
Image preprocessing utilities for ClipBased detection.
"""

import logging
from typing import Union, Tuple

import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Image preprocessing for ClipBased detection models.

    Handles various preprocessing strategies including resize, crop, and normalization.
    """

    def __init__(
        self,
        image_size: int = 224,
        crop_size: int = 224,
        normalize_mean: Tuple[float, float, float] = (0.485, 0.456, 0.406),
        normalize_std: Tuple[float, float, float] = (0.229, 0.224, 0.225),
        preprocessing_type: str = "clip224",
    ):
        """
        Initialize the image preprocessor.

        Args:
            image_size: Size to resize images to
            crop_size: Size for center crop
            normalize_mean: Mean values for normalization
            normalize_std: Standard deviation values for normalization
            preprocessing_type: Type of preprocessing ("clip224", "no_resize", "custom")
        """
        self.image_size = image_size
        self.crop_size = crop_size
        self.normalize_mean = normalize_mean
        self.normalize_std = normalize_std
        self.preprocessing_type = preprocessing_type

        self.transform = self._build_transform()

    def _build_transform(self) -> transforms.Compose:
        """Build the preprocessing transform pipeline."""
        transform_list = []

        if self.preprocessing_type == "clip224":
            # Standard CLIP preprocessing
            transform_list.extend(
                [
                    transforms.Resize(self.image_size, interpolation=transforms.InterpolationMode.BICUBIC),
                    transforms.CenterCrop(self.crop_size),
                ]
            )
        elif self.preprocessing_type == "custom":
            # Custom resize and crop
            transform_list.extend(
                [
                    transforms.Resize((self.image_size, self.image_size)),
                    transforms.CenterCrop(self.crop_size),
                ]
            )
        elif self.preprocessing_type == "no_resize":
            # No resize, just normalize
            pass
        else:
            raise ValueError(f"Unknown preprocessing type: {self.preprocessing_type}")

        # Always convert to tensor and normalize
        transform_list.extend([transforms.ToTensor(), transforms.Normalize(mean=self.normalize_mean, std=self.normalize_std)])

        return transforms.Compose(transform_list)

    def preprocess_image(self, image: Union[str, Image.Image, np.ndarray]) -> torch.Tensor:
        """
        Preprocess a single image.

        Args:
            image: Input image as file path, PIL Image, or numpy array

        Returns:
            Preprocessed image tensor with shape (3, H, W)
        """
        # Convert input to PIL Image
        if isinstance(image, str):
            pil_image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            pil_image = Image.fromarray(image).convert("RGB")
        elif isinstance(image, Image.Image):
            pil_image = image.convert("RGB")
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        # Apply preprocessing
        preprocessed = self.transform(pil_image)

        return preprocessed

    def preprocess_batch(self, images: list) -> torch.Tensor:
        """
        Preprocess a batch of images.

        Args:
            images: List of images (file paths, PIL Images, or numpy arrays)

        Returns:
            Batch tensor with shape (N, 3, H, W)
        """
        preprocessed_images = []

        for image in images:
            try:
                preprocessed = self.preprocess_image(image)
                preprocessed_images.append(preprocessed)
            except Exception as e:
                logger.error(f"Failed to preprocess image {image}: {e}")
                # Skip failed images or use placeholder
                continue

        if not preprocessed_images:
            raise ValueError("No images could be preprocessed successfully")

        # Stack into batch
        batch = torch.stack(preprocessed_images, dim=0)

        return batch

    def validate_image(self, image_path: str) -> bool:
        """
        Validate if an image can be processed.

        Args:
            image_path: Path to the image file

        Returns:
            True if image is valid, False otherwise
        """
        try:
            with Image.open(image_path) as img:
                # Check if image can be loaded and converted to RGB
                img.convert("RGB")
                return True
        except Exception as e:
            logger.warning(f"Invalid image {image_path}: {e}")
            return False

    def get_image_info(self, image: Union[str, Image.Image]) -> dict:
        """
        Get information about an image.

        Args:
            image: Image file path or PIL Image

        Returns:
            Dictionary with image information
        """
        if isinstance(image, str):
            pil_image = Image.open(image)
        else:
            pil_image = image

        return {
            "size": pil_image.size,  # (width, height)
            "mode": pil_image.mode,
            "format": getattr(pil_image, "format", "Unknown"),
            "has_transparency": pil_image.mode in ("RGBA", "LA") or "transparency" in pil_image.info,
        }


def create_clip_preprocessor(config_name: str = "default") -> ImagePreprocessor:
    """
    Create a standard CLIP preprocessor with predefined configurations.

    Args:
        config_name: Configuration name ("default", "large", "small")

    Returns:
        Configured ImagePreprocessor instance
    """
    configs = {
        "default": {"image_size": 224, "crop_size": 224, "preprocessing_type": "clip224"},
        "large": {"image_size": 336, "crop_size": 336, "preprocessing_type": "clip224"},
        "small": {"image_size": 128, "crop_size": 128, "preprocessing_type": "clip224"},
    }

    if config_name not in configs:
        raise ValueError(f"Unknown config: {config_name}. Available: {list(configs.keys())}")

    return ImagePreprocessor(**configs[config_name])
