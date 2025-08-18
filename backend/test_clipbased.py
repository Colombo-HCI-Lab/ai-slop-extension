#!/usr/bin/env python3
"""
Test script for ClipBased image detection system.
"""

import argparse
import sys
from pathlib import Path
from typing import Tuple, List

# ANSI color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color


def print_status(message: str):
    print(f"{GREEN}[TEST]{NC} {message}")


def print_warning(message: str):
    print(f"{YELLOW}[WARN]{NC} {message}")


def print_error(message: str):
    print(f"{RED}[FAIL]{NC} {message}")


def print_success(message: str):
    print(f"{GREEN}[PASS]{NC} {message}")


def test_clipbased_directory() -> bool:
    """Check if ClipBased detection package exists."""
    print_status("Checking ClipBased detection package...")

    clipbased_dir = Path("clipbased_detection")
    if clipbased_dir.exists():
        print_success("ClipBased detection package exists")
        return True
    else:
        print_error("ClipBased detection package not found")
        print_warning("ClipBased package should be in clipbased_detection/")
        return False


def test_clipbased_dependencies() -> bool:
    """Test ClipBased dependencies."""
    print_status("Testing ClipBased dependencies...")

    dependencies = [
        ("open_clip", "OpenCLIP"),
        ("timm", "Timm"),
        ("huggingface_hub", "HuggingFace Hub"),
        ("sklearn", "Scikit-learn"),
        ("pandas", "Pandas"),
        ("tqdm", "TQDM"),
        ("PIL", "Pillow"),
    ]

    all_ok = True
    missing = []

    for module, name in dependencies:
        try:
            __import__(module)
            print(f"  ✓ {name} available")
        except ImportError:
            print(f"  ✗ {name} not available")
            missing.append(module)
            all_ok = False

    if missing:
        print(f"Missing dependencies: {missing}")
        print_warning("Install with: uv sync")

    return all_ok


def test_clipbased_package() -> bool:
    """Test ClipBased detection package."""
    print_status("Testing ClipBased detection package...")

    try:
        sys.path.insert(0, ".")
        from clipbased_detection import ClipBasedImageDetector
        from clipbased_detection.utils import create_test_image
        from clipbased_detection.config import config
        from clipbased_detection.preprocessing import ImagePreprocessor

        print("  ✓ ClipBased package imports successfully")

        # Test configuration
        models = config.get_available_models()
        print(f"  ✓ Available models: {models}")

        return True
    except Exception as e:
        print(f"  ✗ ClipBased package failed: {e}")
        return False


def test_image_preprocessing() -> bool:
    """Test image preprocessing."""
    print_status("Testing image preprocessing...")

    try:
        from clipbased_detection.preprocessing import ImagePreprocessor
        from clipbased_detection.utils import create_test_image

        # Create test image
        test_path = Path("test_clipbased_temp.jpg")
        create_test_image(str(test_path), (224, 224), "checkerboard")
        print("  ✓ Test image created")

        # Test preprocessing
        preprocessor = ImagePreprocessor()
        tensor = preprocessor.preprocess_image(str(test_path))
        print(f"  ✓ Preprocessed tensor shape: {tensor.shape}")

        # Clean up
        test_path.unlink(missing_ok=True)

        return True
    except Exception as e:
        print(f"  ✗ Preprocessing failed: {e}")
        return False


def test_model_config() -> bool:
    """Test model configuration."""
    print_status("Testing model configuration...")

    try:
        from clipbased_detection.config import config

        print(f"  ✓ Default model: {config.default_model}")
        print(f"  ✓ Device: {config.device}")
        print(f"  ✓ Threshold: {config.threshold}")
        print(f"  ✓ Image size: {config.image_size}")

        # Test getting model config
        model_config = config.get_model_config()
        print(f"  ✓ Model config loaded: {model_config.get('arch', 'unknown')}")

        return True
    except Exception as e:
        print(f"  ✗ Configuration failed: {e}")
        return False


def test_api_schemas() -> bool:
    """Test API schemas."""
    print_status("Testing API schemas...")

    try:
        from api.v1.endpoints.image_detection import ImageDetectionResponse, URLImageDetectionRequest
        from typing import List
        from pydantic import BaseModel, Field

        # Local schema for testing
        class AvailableModelsResponse(BaseModel):
            """Response listing available detection models."""

            image_models: List[str] = Field(..., description="Available image detection models")
            video_models: List[str] = Field(..., description="Available video detection models")
            default_image_model: str = Field(..., description="Default image detection model")
            default_video_model: str = Field(..., description="Default video detection model")

        print("  ✓ Image detection schemas imported")

        from api.v1.endpoints.image_detection import router

        print("  ✓ Image detection endpoints imported")

        from core.config import settings

        print(f"  ✓ Max image size: {settings.max_image_size} bytes")
        print(f"  ✓ Default image model: {settings.default_image_model}")

        return True
    except Exception as e:
        print(f"  ✗ API integration failed: {e}")
        return False


def test_model_weights() -> bool:
    """Check model weights."""
    print_status("Checking model weights...")

    weights_dir = Path("clipbased_detection/weights")

    if weights_dir.exists() and any(weights_dir.iterdir()):
        print_success("Model weights directory exists with files")
        # List first few directories/files
        items = list(weights_dir.iterdir())[:5]
        for item in items:
            print(f"  - {item.name}")
        return True
    else:
        print_warning(f"No pre-trained weights found in {weights_dir}")
        print_status("Models will download automatically from HuggingFace on first use")
        return True  # Don't fail, weights are optional


def test_utilities() -> bool:
    """Test utility functions."""
    print_status("Testing utility functions...")

    try:
        from clipbased_detection.utils import create_test_image, validate_image_file, get_image_hash, resize_image_if_needed

        # Test creating different patterns
        test_path = Path("test_util_temp.jpg")
        for pattern in ["checkerboard", "gradient", "noise"]:
            create_test_image(str(test_path), (128, 128), pattern)
            print(f"  ✓ Created {pattern} test image")

            # Validate the image
            if validate_image_file(str(test_path)):
                print(f"  ✓ Image validation passed")

            # Get image hash
            hash_val = get_image_hash(str(test_path))
            print(f"  ✓ Image hash: {hash_val[:16]}...")

            test_path.unlink(missing_ok=True)

        return True
    except Exception as e:
        print(f"  ✗ Utilities test failed: {e}")
        return False


def test_image_endpoints() -> bool:
    """Test image detection API endpoints."""
    print_status("Testing image detection API endpoints...")

    try:
        import requests
        from clipbased_detection.utils import create_test_image

        # Check if API is running
        api_url = "http://localhost:4001"
        try:
            response = requests.get(f"{api_url}/api/v1/health", timeout=2)
            if response.status_code != 200:
                print_error("API not running or not healthy")
                print_status("Start with: uv run uvicorn main:app --host 0.0.0.0 --port 4001")
                return False
        except requests.exceptions.RequestException:
            print_error("API not accessible at http://localhost:4001")
            print_status("Start with: uv run uvicorn main:app --host 0.0.0.0 --port 4001")
            return False

        print("  ✓ API is running")

        # Test available models endpoint
        response = requests.get(f"{api_url}/api/v1/image/models")
        if response.status_code == 200:
            models = response.json()
            print(f"  ✓ Image models endpoint: {models.get('image_models', [])[:3]}")
        else:
            print(f"  ✗ Image models endpoint failed: {response.status_code}")
            return False

        # Test image upload endpoint
        test_image = Path("test_api_image.jpg")
        create_test_image(str(test_image), (224, 224), "checkerboard")

        with open(test_image, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            data = {"model_name": "clipbased", "threshold": "0.0"}
            response = requests.post(f"{api_url}/api/v1/image/detect", files=files, data=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Image upload endpoint works")
            if "detection_result" in result:
                detection = result["detection_result"]
                print(f"    AI Generated: {detection.get('is_ai_generated', 'N/A')}")
                print(f"    Confidence: {detection.get('confidence', 0):.3f}")
                print(f"    Model: {detection.get('model_used', 'N/A')}")
        else:
            print(f"  ✗ Image upload failed: {response.status_code}")
            if response.text:
                print(f"    Error: {response.text[:200]}")
            return False

        # Test image URL endpoint
        test_url = "https://picsum.photos/200"  # Random image service
        response = requests.post(f"{api_url}/api/v1/image/detect-url", json={"image_url": test_url, "model_name": "clipbased"}, timeout=30)

        if response.status_code == 200:
            print(f"  ✓ Image URL endpoint works")
        else:
            # URL endpoint might fail due to network, don't fail the test
            print(f"  ⚠ Image URL endpoint: {response.status_code} (non-critical)")

        # Clean up
        test_image.unlink(missing_ok=True)

        return True

    except ImportError:
        print_warning("requests library not available, skipping endpoint tests")
        print_status("Install with: pip install requests")
        return True
    except Exception as e:
        print_error(f"Endpoint testing failed: {e}")
        return False


def run_tests(tests: List[Tuple[str, callable]]) -> Tuple[int, int]:
    """Run a list of tests and return pass/fail counts."""
    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print()  # Add spacing between tests
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print_error(f"{test_name} exception: {e}")
            failed += 1

    return passed, failed


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test ClipBased image detection system")
    parser.add_argument("--quick", action="store_true", help="Run only essential tests (skip weights check)")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    print("================================")
    print("ClipBased Image Detection Tests")
    print("================================")

    # Define tests
    tests = [
        ("ClipBased Directory", test_clipbased_directory),
        ("Dependencies", test_clipbased_dependencies),
        ("Package Import", test_clipbased_package),
        ("Image Preprocessing", test_image_preprocessing),
        ("Model Config", test_model_config),
        ("API Schemas", test_api_schemas),
    ]

    # Add optional tests
    if not args.quick:
        tests.append(("Model Weights", test_model_weights))
        tests.append(("Utilities", test_utilities))

    # Always test API endpoints
    tests.append(("API Endpoints", test_image_endpoints))

    # Run tests
    passed, failed = run_tests(tests)

    # Print summary
    print()
    print("================================")
    print("Test Summary")
    print("================================")
    print(f"{GREEN}Passed:{NC} {passed}")
    print(f"{RED}Failed:{NC} {failed}")

    if failed == 0:
        print()
        print(f"{GREEN}✓ All ClipBased tests passed!{NC}")
        print()
        print("Next steps:")
        print("  1. Start API: uv run uvicorn main:app --host 0.0.0.0 --port 4001 --reload")
        print('  2. Test endpoint: curl -X POST "http://localhost:4001/api/v1/image/detect" -F "file=@image.jpg"')
        print('  3. Check models: curl "http://localhost:4001/api/v1/image/models"')
        sys.exit(0)
    else:
        print()
        print(f"{RED}✗ Some tests failed{NC}")
        print()
        print("To fix issues:")
        print("  1. Install dependencies: uv sync")
        print("  2. Activate environment: source .venv/bin/activate")
        print("  3. Check clipbased_detection/ package exists")
        sys.exit(1)


if __name__ == "__main__":
    main()
