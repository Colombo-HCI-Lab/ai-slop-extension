"""
Lightweight Protocol interfaces for detection services.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Protocol, Union

from schemas.image_detection import ImageDetectionResponse
from schemas.video_detection import DetectionResponse


class VideoDetectionServiceProtocol(Protocol):
    model_name: str
    device: str

    async def process_video_file_async(
        self,
        video_path: Union[str, Path],
        top_k: Optional[int] = None,
        job_id=None,
        model_name: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> DetectionResponse: ...

    def get_supported_formats(self) -> List[str]: ...

    def get_model_info(self) -> Dict: ...

    def validate_video_file(self, file_path: Union[str, Path]) -> bool: ...

    def set_threshold(self, threshold: float) -> None: ...

    def cleanup(self) -> None: ...


class ImageDetectionServiceProtocol(Protocol):
    model_name: str
    device: str

    async def process_image_file_async(
        self, image_path: Union[str, Path], threshold: Optional[float] = None, job_id=None
    ) -> ImageDetectionResponse: ...

    def get_supported_formats(self) -> List[str]: ...

    def get_available_models(self) -> List[str]: ...

    def get_model_info(self) -> Dict: ...

    def validate_image_file(self, file_path: Union[str, Path]) -> bool: ...

    def set_threshold(self, threshold: float) -> None: ...

    def cleanup(self) -> None: ...
