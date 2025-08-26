"""
Utility functions for ClipBased detection.
"""

import hashlib
import io
import logging
from typing import Union, Tuple, Optional

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def create_test_image(
    output_path: str,
    size: Tuple[int, int] = (512, 512),
    pattern: str = "checkerboard",
    colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (0, 0, 0)),
) -> str:
    """
    Create a test image for development and testing purposes.

    Args:
        output_path: Path where the test image will be saved
        size: Image dimensions (width, height)
        pattern: Pattern type ("checkerboard", "gradient", "noise", "solid")
        colors: Two colors to use for the pattern (RGB tuples)

    Returns:
        Path to the created test image
    """
    width, height = size

    if pattern == "checkerboard":
        # Create checkerboard pattern
        image = Image.new("RGB", size, colors[0])
        draw = ImageDraw.Draw(image)

        square_size = min(width, height) // 8
        for i in range(0, width, square_size):
            for j in range(0, height, square_size):
                if (i // square_size + j // square_size) % 2:
                    draw.rectangle([i, j, i + square_size, j + square_size], fill=colors[1])

    elif pattern == "gradient":
        # Create horizontal gradient
        image = Image.new("RGB", size)
        for x in range(width):
            r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * x / width)
            g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * x / width)
            b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * x / width)
            for y in range(height):
                image.putpixel((x, y), (r, g, b))

    elif pattern == "noise":
        # Create random noise
        noise_array = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        image = Image.fromarray(noise_array)

    elif pattern == "solid":
        # Create solid color
        image = Image.new("RGB", size, colors[0])

    else:
        raise ValueError(f"Unknown pattern type: {pattern}")

    # Add text overlay
    draw = ImageDraw.Draw(image)
    try:
        # Try to use a default font
        font = ImageFont.load_default()
    except:
        font = None

    text = f"Test Image ({pattern})"
    if font:
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position text in center
        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # Draw text with background
        draw.rectangle([x - 5, y - 5, x + text_width + 5, y + text_height + 5], fill=(128, 128, 128))
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

    # Save image
    image.save(output_path)
    logger.info(f"Created test image: {output_path} ({width}x{height}, {pattern})")

    return output_path


def download_image_from_url(
    url: str,
    max_size: int = 10 * 1024 * 1024,  # 10MB
    timeout: int = 30,
) -> Image.Image:
    """
    Download an image from a URL.

    Args:
        url: URL of the image to download
        max_size: Maximum file size in bytes
        timeout: Request timeout in seconds

    Returns:
        PIL Image object
    """
    try:
        # Set headers to mimic a browser request
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        # Download image with streaming to check size
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()

        # Check content length if provided
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            raise ValueError(f"Image too large: {content_length} bytes (max: {max_size})")

        # Download content with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size:
                raise ValueError(f"Image too large: {len(content)} bytes (max: {max_size})")

        # Load image from bytes
        image = Image.open(io.BytesIO(content))
        image = image.convert("RGB")  # Ensure RGB format

        logger.info(f"Downloaded image from {url}: {image.size}")
        return image

    except requests.RequestException as e:
        logger.error(f"Failed to download image from {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to process image from {url}: {e}")
        raise


def validate_image_file(file_path: str) -> bool:
    """
    Validate if a file is a valid image.

    Args:
        file_path: Path to the image file

    Returns:
        True if valid image, False otherwise
    """
    try:
        with Image.open(file_path) as img:
            img.verify()  # Verify it's a valid image
        return True
    except Exception:
        return False


def get_image_hash(image: Union[str, Image.Image, np.ndarray]) -> str:
    """
    Calculate MD5 hash of an image for caching/deduplication.

    Args:
        image: Input image

    Returns:
        MD5 hash string
    """
    if isinstance(image, str):
        # File path
        with open(image, "rb") as f:
            content = f.read()
    elif isinstance(image, Image.Image):
        # PIL Image
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        content = buffer.getvalue()
    elif isinstance(image, np.ndarray):
        # Numpy array
        content = image.tobytes()
    else:
        raise ValueError(f"Unsupported image type: {type(image)}")

    return hashlib.md5(content).hexdigest()


def resize_image_if_needed(image: Image.Image, max_size: Tuple[int, int] = (1024, 1024), maintain_aspect_ratio: bool = True) -> Image.Image:
    """
    Resize image if it exceeds maximum dimensions.

    Args:
        image: PIL Image to resize
        max_size: Maximum dimensions (width, height)
        maintain_aspect_ratio: Whether to maintain aspect ratio

    Returns:
        Resized PIL Image
    """
    width, height = image.size
    max_width, max_height = max_size

    if width <= max_width and height <= max_height:
        return image

    if maintain_aspect_ratio:
        # Calculate scaling factor
        scale = min(max_width / width, max_height / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
    else:
        new_width, new_height = max_size

    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

    return resized


def save_detection_results_csv(results: list, output_path: str) -> None:
    """
    Save detection results to CSV file.

    Args:
        results: List of detection result dictionaries
        output_path: Path to output CSV file
    """
    import csv

    if not results:
        logger.warning("No results to save")
        return

    # Get all possible fieldnames from results
    fieldnames = set()
    for result in results:
        fieldnames.update(result.keys())
        if "metadata" in result and isinstance(result["metadata"], dict):
            for key in result["metadata"].keys():
                fieldnames.add(f"metadata_{key}")

    fieldnames = sorted(fieldnames)

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            # Flatten metadata
            row = result.copy()
            if "metadata" in row and isinstance(row["metadata"], dict):
                metadata = row.pop("metadata")
                for key, value in metadata.items():
                    row[f"metadata_{key}"] = value

            writer.writerow(row)

    logger.info(f"Saved {len(results)} results to {output_path}")


def create_comparison_image(original: Image.Image, results: dict, output_path: str = None) -> Optional[str]:
    """
    Create a comparison image showing original with detection results.

    Args:
        original: Original PIL Image
        results: Detection results dictionary
        output_path: Output path for comparison image

    Returns:
        Path to created comparison image if output_path provided
    """
    # Create a new image with space for text
    width, height = original.size
    text_height = 150
    comparison = Image.new("RGB", (width, height + text_height), (255, 255, 255))

    # Paste original image
    comparison.paste(original, (0, 0))

    # Add text overlay with results
    draw = ImageDraw.Draw(comparison)

    try:
        font = ImageFont.load_default()
    except:
        font = None

    y_offset = height + 10
    line_height = 20

    # Format results text
    text_lines = [
        f"AI Generated: {results.get('is_ai_generated', 'Unknown')}",
        f"Confidence: {results.get('confidence', 0):.3f}",
        f"LLR Score: {results.get('llr_score', 0):.3f}",
        f"Model: {results.get('model_used', 'Unknown')}",
        f"Time: {results.get('processing_time', 0):.3f}s",
    ]

    for i, line in enumerate(text_lines):
        draw.text((10, y_offset + i * line_height), line, fill=(0, 0, 0), font=font)

    if output_path:
        comparison.save(output_path)
        logger.info(f"Created comparison image: {output_path}")
        return output_path

    return comparison


def benchmark_detector(detector, test_images: list, num_runs: int = 5) -> dict:
    """
    Benchmark a ClipBased detector's performance.

    Args:
        detector: ClipBasedImageDetector instance
        test_images: List of test images
        num_runs: Number of benchmark runs

    Returns:
        Benchmark results dictionary
    """
    import time

    times = []
    results = []

    for run in range(num_runs):
        start_time = time.time()

        for image in test_images:
            result = detector.detect_image(image)
            results.append(result)

        run_time = time.time() - start_time
        times.append(run_time)

        logger.info(f"Benchmark run {run + 1}/{num_runs}: {run_time:.3f}s")

    avg_time = np.mean(times)
    avg_time_per_image = avg_time / len(test_images)

    return {
        "total_runs": num_runs,
        "total_images": len(test_images),
        "average_total_time": avg_time,
        "average_time_per_image": avg_time_per_image,
        "images_per_second": 1.0 / avg_time_per_image,
        "run_times": times,
        "sample_results": results[:5],  # First 5 results as samples
    }
