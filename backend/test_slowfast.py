#!/usr/bin/env python3
"""
Test script for SlowFast video detection system.
"""

import argparse
import subprocess
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


def test_slowfast_directory() -> bool:
    """Check if SlowFast detection package exists."""
    print_status("Checking SlowFast detection package...")

    slowfast_dir = Path("slowfast_detection")
    if slowfast_dir.exists():
        print_success("SlowFast detection package exists")
        return True
    else:
        print_error("SlowFast detection package not found")
        print_warning("SlowFast package should be in slowfast_detection/")
        return False


def test_slowfast_imports() -> bool:
    """Test SlowFast detection package imports."""
    print_status("Testing SlowFast detection package imports...")

    try:
        from slowfast_detection import AIVideoDetector, VideoPreprocessor, create_test_video
        from slowfast_detection.slowfast import config

        print("  ✓ SlowFast detection package imports successfully")
        print("  ✓ SlowFast core modules available")
        return True
    except ImportError as e:
        print(f"  ✗ SlowFast detection import failed: {e}")
        return False


def test_video_dependencies() -> bool:
    """Test video processing dependencies."""
    print_status("Testing video processing dependencies...")

    dependencies = [
        ("torch", "PyTorch"),
        ("pytorchvideo", "PyTorchVideo"),
        ("cv2", "OpenCV"),
        ("av", "PyAV"),
        ("torchvision", "TorchVision"),
    ]

    all_ok = True
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"  ✓ {name} available")
        except ImportError:
            print(f"  ✗ {name} not available")
            all_ok = False

    if not all_ok:
        print_warning("Install missing dependencies with: uv sync")

    return all_ok


def test_video_detection_package() -> bool:
    """Test video detection package."""
    print_status("Testing video detection package...")

    try:
        sys.path.insert(0, ".")
        from slowfast_detection import VideoPreprocessor, AIVideoDetector, create_test_video

        print("  ✓ Video detection package imports successfully")

        # Test creating a test video
        test_path = Path("test_video_temp.mp4")
        create_test_video(str(test_path), duration_seconds=1, fps=10)
        print("  ✓ Test video creation works")
        test_path.unlink(missing_ok=True)
        return True

    except Exception as e:
        print(f"  ✗ Video detection package failed: {e}")
        return False


def test_cli_interface() -> bool:
    """Test CLI interface."""
    print_status("Testing CLI interface...")

    if not Path("detect_video.py").exists():
        print_error("detect_video.py not found")
        return False

    try:
        result = subprocess.run([sys.executable, "detect_video.py", "--help"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print_success("CLI interface works")
            return True
        else:
            print_error("CLI interface failed")
            return False
    except Exception as e:
        print_error(f"CLI test failed: {e}")
        return False


def test_sample_video() -> bool:
    """Test sample video detection."""
    print_status("Testing sample video detection...")

    sample_path = Path("sample.mp4")

    # Create sample video if it doesn't exist
    if not sample_path.exists():
        print_status("Creating sample video...")
        try:
            from slowfast_detection import create_test_video

            create_test_video(str(sample_path), duration_seconds=2, fps=15)
        except Exception as e:
            print_warning(f"Could not create sample video: {e}")
            return False

    # Test stats-only mode (faster)
    try:
        result = subprocess.run(
            [sys.executable, "detect_video.py", "--stats-only", str(sample_path)], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print_success("Video detection works")
            return True
        else:
            print_error("Video detection failed")
            if result.stderr:
                print(f"  Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print_error(f"Video detection test failed: {e}")
        return False


def test_video_endpoints() -> bool:
    """Test video detection API endpoints."""
    print_status("Testing video detection API endpoints...")

    try:
        import requests
        import time
        from slowfast_detection import create_test_video

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

        # Test health endpoint
        response = requests.get(f"{api_url}/api/v1/health")
        if response.status_code == 200:
            print("  ✓ Health endpoint works")
        else:
            print(f"  ✗ Health endpoint failed: {response.status_code}")
            return False

        # Test available models endpoint
        response = requests.get(f"{api_url}/api/v1/image/models")
        if response.status_code == 200:
            models = response.json()
            video_models = models.get("video_models", [])
            print(f"  ✓ Video models endpoint works: {video_models}")
        else:
            print(f"  ✗ Video models endpoint failed: {response.status_code}")
            return False

        # Test video upload endpoint
        test_video = Path("test_api_video.mp4")
        if not test_video.exists():
            create_test_video(str(test_video), duration_seconds=1, fps=10)

        with open(test_video, "rb") as f:
            files = {"file": ("test.mp4", f, "video/mp4")}
            data = {"model_name": "slowfast_r50"}
            response = requests.post(f"{api_url}/api/v1/video/detect", files=files, data=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Video upload endpoint works")
            if "detection_result" in result:
                detection = result["detection_result"]
                print(f"    AI Generated: {detection.get('is_ai_generated', 'N/A')}")
                print(f"    Confidence: {detection.get('confidence', 0):.3f}")
                print(f"    Model: {detection.get('model_used', 'N/A')}")
            else:
                print(f"    Status: {result.get('status', 'N/A')}")
        else:
            print(f"  ✗ Video upload failed: {response.status_code}")
            return False

        # Clean up
        test_video.unlink(missing_ok=True)

        return True

    except ImportError:
        print_error("requests library not available for endpoint tests")
        print_status("Install with: pip install requests or uv sync")
        return False
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
    parser = argparse.ArgumentParser(description="Test SlowFast video detection system")
    parser.add_argument("--quick", action="store_true", help="Run only essential tests (skip sample video)")
    args = parser.parse_args()

    print("================================")
    print("SlowFast Video Detection Tests")
    print("================================")

    # Define tests
    tests = [
        ("SlowFast Directory", test_slowfast_directory),
        ("SlowFast Imports", test_slowfast_imports),
        ("Video Dependencies", test_video_dependencies),
        ("Detection Package", test_video_detection_package),
        ("CLI Interface", test_cli_interface),
    ]

    # Add additional tests unless in quick mode
    if not args.quick:
        tests.append(("Sample Video", test_sample_video))

    # Always test API endpoints
    tests.append(("API Endpoints", test_video_endpoints))

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
        print(f"{GREEN}✓ All SlowFast tests passed!{NC}")
        print()
        print("Next steps:")
        print("  1. Run video detection: python detect_video.py sample.mp4")
        print("  2. Start API: uv run uvicorn main:app --host 0.0.0.0 --port 4001 --reload")
        sys.exit(0)
    else:
        print()
        print(f"{RED}✗ Some tests failed{NC}")
        print()
        print("To fix issues:")
        print("  1. Install dependencies: uv sync")
        print("  2. Activate environment: source .venv/bin/activate")
        print("  3. Check slowfast_detection/ package exists")
        sys.exit(1)


if __name__ == "__main__":
    main()
