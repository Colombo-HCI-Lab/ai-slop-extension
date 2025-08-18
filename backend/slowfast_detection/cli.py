"""
Command-line interface for AI video detection.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Conditional imports for when dependencies are available
try:
    from .preprocessing import VideoPreprocessor
    from .detection import AIVideoDetector
    from .utils import create_test_video, setup_logging, get_video_stats

    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Dependencies not available: {e}")
    VideoPreprocessor = None
    AIVideoDetector = None
    create_test_video = None
    setup_logging = None
    get_video_stats = None
    DEPENDENCIES_AVAILABLE = False

logger = logging.getLogger(__name__)


class DetectionCLI:
    """Command-line interface for AI video detection."""

    def __init__(self):
        self.preprocessor = None
        self.detector = None

    def create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            description="AI-generated video detection using SlowFast models",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s video.mp4                              # Detect AI content in video
  %(prog)s --create-test-video test.mp4           # Create test video
  %(prog)s --demo-hub video.mp4                   # Quick demo mode
  %(prog)s --model slowfast_r101 --threshold 0.3  # Custom model and threshold
            """,
        )

        parser.add_argument("video_path", type=str, help="Path to video file or output path for test video")

        # Model options
        parser.add_argument(
            "--model",
            type=str,
            default="slowfast_r50",
            choices=["slowfast_r50", "slowfast_r101"],
            help="SlowFast model to use (default: slowfast_r50)",
        )

        # Detection options
        parser.add_argument("--threshold", type=float, default=0.5, help="AI detection threshold 0.0-1.0 (default: 0.5)")

        # Processing options
        parser.add_argument(
            "--device", type=str, default=None, choices=["auto", "cpu", "cuda"], help="Device for inference (default: auto)"
        )

        # Modes
        parser.add_argument("--demo-hub", action="store_true", help="Quick demo mode using pytorchvideo hub models")

        parser.add_argument("--create-test-video", action="store_true", help="Create a test video file for testing")

        parser.add_argument("--stats-only", action="store_true", help="Only show video statistics without detection")

        # Output options
        parser.add_argument("--output", type=str, default=None, help="Output JSON file path (default: video_path.json)")

        parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output messages")

        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

        return parser

    def handle_test_video_creation(self, args) -> bool:
        """Handle test video creation."""
        video_path = Path(args.video_path)

        logger.info(f"Creating test video: {video_path}")
        success = create_test_video(video_path)

        if success:
            if not args.quiet:
                print(f"✓ Test video created successfully: {video_path}")
            return True
        else:
            if not args.quiet:
                print(f"✗ Failed to create test video: {video_path}")
            return False

    def handle_video_stats(self, args) -> bool:
        """Handle video statistics display."""
        video_path = Path(args.video_path)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False

        try:
            stats = get_video_stats(video_path)

            if not args.quiet:
                print(f"\nVideo Statistics for {video_path.name}:")
                print("=" * 50)
                print(f"File Size: {stats['file_size_mb']:.1f} MB")
                print(f"Resolution: {stats['resolution']}")
                print(f"Duration: {stats['duration_formatted']}")
                print(f"Frame Count: {stats['frame_count']}")
                print(f"FPS: {stats['fps']:.2f}")
                print(f"Codec: {stats['codec']}")

            return True

        except Exception as e:
            logger.error(f"Error getting video statistics: {e}")
            return False

    def initialize_models(self, args) -> bool:
        """Initialize preprocessor and detector."""
        try:
            # Initialize preprocessor
            self.preprocessor = VideoPreprocessor()

            # Initialize detector
            device = None if args.device == "auto" else args.device
            self.detector = AIVideoDetector(model_name=args.model, device=device, ai_threshold=args.threshold)

            logger.info("Models initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            return False

    def run_detection(self, args) -> bool:
        """Run AI detection on video."""
        video_path = Path(args.video_path)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False

        try:
            start_time = time.time()

            if not args.quiet:
                print(f"Processing video: {video_path.name}")
                print("Extracting and preprocessing frames...")

            # Process video
            slowfast_input = self.preprocessor.process_video(video_path)

            if not args.quiet:
                print("Running AI detection inference...")

            # Run detection
            result = self.detector.predict(slowfast_input)

            processing_time = time.time() - start_time
            result["processing_time_seconds"] = processing_time

            # Display results
            if not args.quiet:
                self.display_results(video_path, result)

            # Save results
            self.save_results(video_path, result, args)

            return True

        except Exception as e:
            logger.error(f"Error during detection: {e}")
            import traceback

            traceback.print_exc()
            return False

    def display_results(self, video_path: Path, result: dict):
        """Display detection results."""
        print(f"\nAI-Generated Video Detection Results for {video_path.name}:")
        print("=" * 60)
        print(f"Is AI-Generated: {'YES' if result['is_ai_generated'] else 'NO'}")
        print(f"Confidence: {result['confidence']:.4f}")
        print(f"AI Probability: {result['ai_probability']:.4f}")
        print(f"Threshold Used: {result['threshold_used']:.2f}")
        print(f"Model Used: {result['model_used']}")
        print(f"Processing Time: {result['processing_time_seconds']:.2f}s")

    def save_results(self, video_path: Path, result: dict, args):
        """Save results to JSON file."""
        # Determine output file path
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = video_path.with_suffix(".json")

        # Prepare output data
        output_data = {
            "video_path": str(video_path),
            "model": args.model,
            "detection_result": result,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cli_args": {"model": args.model, "threshold": args.threshold, "device": args.device},
        }

        # Save to file
        try:
            with open(output_path, "w") as f:
                json.dump(output_data, f, indent=2)

            if not args.quiet:
                print(f"\nDetailed results saved to: {output_path}")

        except Exception as e:
            logger.error(f"Failed to save results to {output_path}: {e}")

    def cleanup(self):
        """Clean up resources."""
        if self.detector:
            self.detector.cleanup()

    def run(self, args=None) -> int:
        """Main CLI entry point."""
        parser = self.create_parser()
        args = parser.parse_args(args)

        # Check if dependencies are available
        if not DEPENDENCIES_AVAILABLE:
            print("Error: Required dependencies are not installed.")
            print("Please run: ./setup.sh")
            print("Then activate the virtual environment: source .venv/bin/activate")
            return 1

        # Setup logging
        log_level = "DEBUG" if args.verbose else "WARNING" if args.quiet else "INFO"
        setup_logging(log_level)

        try:
            # Handle test video creation
            if args.create_test_video:
                success = self.handle_test_video_creation(args)
                return 0 if success else 1

            # Handle stats only mode
            if args.stats_only:
                success = self.handle_video_stats(args)
                return 0 if success else 1

            # Initialize models for detection
            if not self.initialize_models(args):
                return 1

            # Run detection
            success = self.run_detection(args)

            # Cleanup
            self.cleanup()

            return 0 if success else 1

        except KeyboardInterrupt:
            logger.info("Detection interrupted by user")
            self.cleanup()
            return 130
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.cleanup()
            return 1


def main():
    """Entry point for CLI."""
    cli = DetectionCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
