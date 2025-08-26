"""Download SlowFast pretrained models on demand."""

from pathlib import Path

import pytorchvideo.models.hub as hub
import torch


def download_slowfast_models(models_dir: Path | None = None):
    """Download SlowFast models if they don't exist."""
    if models_dir is None:
        models_dir = Path(__file__).parent / "models"

    models_dir.mkdir(exist_ok=True)

    models_to_download = {
        "slowfast_r50_pretrained.pth": hub.slowfast_r50,
        "slowfast_r101_pretrained.pth": hub.slowfast_r101,
    }

    for filename, model_fn in models_to_download.items():
        model_path = models_dir / filename
        if not model_path.exists():
            print(f"Downloading {filename}...")
            model = model_fn(pretrained=True)
            torch.save(model.state_dict(), model_path)
            print(f"✓ {filename} saved ({model_path.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            print(f"✓ {filename} already exists")

    return models_dir


if __name__ == "__main__":
    download_slowfast_models()
