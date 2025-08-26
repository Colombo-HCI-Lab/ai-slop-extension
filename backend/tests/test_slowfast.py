import pytest
from pathlib import Path


def test_slowfast_module_exists():
    assert Path("ml/slowfast/impl").exists(), "Expected ml/slowfast/impl to exist"


def test_slowfast_imports_available():
    m = pytest.importorskip("ml.slowfast")
    # Only check exported symbols; don't instantiate (would load models)
    assert hasattr(m, "AIVideoDetector")
    assert hasattr(m, "VideoPreprocessor")


def test_create_test_video_and_preprocessor(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("cv2")

    from ml.slowfast.impl import create_test_video
    from ml.slowfast import VideoPreprocessor

    video_path = tmp_path / "sample.mp4"
    ok = create_test_video(video_path, duration_seconds=1, fps=8)
    assert ok and video_path.exists()

    pre = VideoPreprocessor(num_frames=8, frames_per_second=8)
    info = pre.get_video_info(video_path)
    assert info["fps"] > 0
    slowfast_input, meta = pre.process_video(video_path)
    assert isinstance(slowfast_input, list) and len(slowfast_input) == 2

