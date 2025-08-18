"""
Video preprocessing utilities for SlowFast models.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Union

import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)


class VideoPreprocessor:
    """Handles video preprocessing for SlowFast models."""

    def __init__(
        self,
        side_size: int = 256,
        crop_size: int = 224,
        num_frames: int = 32,
        sampling_rate: int = 2,
        frames_per_second: int = 30,
        alpha: int = 4,
    ):
        """
        Initialize video preprocessor with configuration.

        Args:
            side_size: Size of the shorter side after resizing
            crop_size: Size of the center crop
            num_frames: Number of frames to sample
            sampling_rate: Frame sampling rate
            frames_per_second: Target FPS for preprocessing
            alpha: SlowFast alpha parameter (fast pathway frame rate)
        """
        self.side_size = side_size
        self.crop_size = crop_size
        self.num_frames = num_frames
        self.sampling_rate = sampling_rate
        self.frames_per_second = frames_per_second
        self.alpha = alpha

        # Kinetics-400 normalization parameters
        self.mean = [0.45, 0.45, 0.45]
        self.std = [0.225, 0.225, 0.225]

        logger.info(
            f"VideoPreprocessor initialized with: "
            f"frames={self.num_frames}, crop={self.crop_size}, "
            f"side={self.side_size}, alpha={self.alpha}"
        )

    def extract_frames(self, video_path: Union[str, Path]) -> List[np.ndarray]:
        """
        Extract frames from video file.

        Args:
            video_path: Path to video file

        Returns:
            List of frames as numpy arrays

        Raises:
            ValueError: If video cannot be opened
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        # Get video metadata
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame)

        cap.release()

        logger.info(f"Extracted {len(frames)} frames from video (fps={fps:.2f}, duration={duration:.2f}s)")

        if not frames:
            raise ValueError("No frames extracted from video")

        return frames

    def get_video_info(self, video_path: Union[str, Path]) -> dict:
        """
        Get video metadata information.

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with video metadata
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0

        cap.release()

        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration": duration,
            "resolution": f"{width}x{height}",
        }

    def preprocess_frames(self, frames: List[np.ndarray]) -> torch.Tensor:
        """
        Preprocess frames for SlowFast model.

        Args:
            frames: List of frame arrays

        Returns:
            Preprocessed video tensor
        """
        if len(frames) < self.num_frames:
            # Repeat frames if video is too short
            repeat_factor = (self.num_frames // len(frames)) + 1
            frames = frames * repeat_factor
            logger.warning(f"Video too short, repeated frames {repeat_factor} times")

        # Uniform temporal sampling
        indices = np.linspace(0, len(frames) - 1, self.num_frames, dtype=int)
        sampled_frames = [frames[i] for i in indices]

        # Convert to numpy array and normalize to [0, 1]
        frames_array = np.array(sampled_frames, dtype=np.float32) / 255.0

        # Resize frames
        resized_frames = []
        for frame in frames_array:
            resized_frame = self._resize_frame(frame)
            resized_frames.append(resized_frame)

        # Center crop
        cropped_frames = []
        for frame in resized_frames:
            cropped_frame = self._center_crop(frame)
            cropped_frames.append(cropped_frame)

        # Convert to tensor and normalize
        video_tensor = torch.from_numpy(np.array(cropped_frames))
        video_tensor = video_tensor.permute(3, 0, 1, 2)  # (C, T, H, W)

        # Normalize with Kinetics-400 parameters
        for i in range(3):
            video_tensor[i] = (video_tensor[i] - self.mean[i]) / self.std[i]

        logger.debug(f"Preprocessed video tensor shape: {video_tensor.shape}")
        return video_tensor

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame maintaining aspect ratio."""
        h, w = frame.shape[:2]
        if h < w:
            new_h, new_w = self.side_size, int(self.side_size * w / h)
        else:
            new_h, new_w = int(self.side_size * h / w), self.side_size

        return cv2.resize(frame, (new_w, new_h))

    def _center_crop(self, frame: np.ndarray) -> np.ndarray:
        """Apply center crop to frame."""
        h, w = frame.shape[:2]
        start_h = max(0, (h - self.crop_size) // 2)
        start_w = max(0, (w - self.crop_size) // 2)

        # Handle case where frame is smaller than crop size
        end_h = min(h, start_h + self.crop_size)
        end_w = min(w, start_w + self.crop_size)

        cropped = frame[start_h:end_h, start_w:end_w]

        # Pad if necessary
        if cropped.shape[0] < self.crop_size or cropped.shape[1] < self.crop_size:
            pad_h = max(0, self.crop_size - cropped.shape[0])
            pad_w = max(0, self.crop_size - cropped.shape[1])
            cropped = np.pad(cropped, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant", constant_values=0)

        return cropped[: self.crop_size, : self.crop_size]

    def create_slowfast_input(self, video_tensor: torch.Tensor) -> List[torch.Tensor]:
        """
        Create SlowFast dual-pathway input.

        Args:
            video_tensor: Preprocessed video tensor (C, T, H, W)

        Returns:
            List containing [slow_pathway, fast_pathway] tensors
        """
        # Fast pathway: all frames
        fast_pathway = video_tensor

        # Slow pathway: every alpha-th frame
        slow_indices = torch.arange(0, video_tensor.size(1), self.alpha)
        slow_pathway = video_tensor[:, slow_indices]

        # Add batch dimension
        fast_pathway = fast_pathway.unsqueeze(0)
        slow_pathway = slow_pathway.unsqueeze(0)

        logger.debug(f"SlowFast input shapes - Slow: {slow_pathway.shape}, Fast: {fast_pathway.shape}")

        return [slow_pathway, fast_pathway]

    def process_video(self, video_path: Union[str, Path]) -> Tuple[List[torch.Tensor], dict]:
        """
        Complete video processing pipeline.

        Args:
            video_path: Path to video file

        Returns:
            Tuple of (slowfast_input, video_info)
        """
        # Get video metadata
        video_info = self.get_video_info(video_path)

        # Extract and preprocess frames
        frames = self.extract_frames(video_path)
        video_tensor = self.preprocess_frames(frames)
        slowfast_input = self.create_slowfast_input(video_tensor)

        return slowfast_input, video_info
