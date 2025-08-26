import pytest
from pathlib import Path


def test_clipbased_module_exists():
    assert Path("ml/clipbased/impl").exists(), "Expected ml/clipbased/impl to exist"


def test_clipbased_imports_available():
    # Only import symbols; avoid heavy initialization/downloads
    m = pytest.importorskip("ml.clipbased")
    assert hasattr(m, "ClipBasedImageDetector")


def test_clipbased_utils_and_preprocessing(tmp_path):
    # Skip if heavy deps are missing
    pytest.importorskip("torch")
    pytest.importorskip("PIL")

    from ml.clipbased.impl.utils import create_test_image
    from ml.clipbased.impl.preprocessing import ImagePreprocessor

    img_path = tmp_path / "test_img.jpg"
    create_test_image(str(img_path), (224, 224), pattern="checkerboard")
    assert img_path.exists()

    pre = ImagePreprocessor()
    tensor = pre.preprocess_image(str(img_path))
    # Basic shape checks: (C, H, W) or (1, C, H, W) depending on impl
    assert hasattr(tensor, "shape")
    assert len(tensor.shape) in (3, 4)
