# SlowFast Pretrained Models

This directory contains pretrained SlowFast models for AI video detection.

## Required Models

- `slowfast_r50_pretrained.pth` (133 MB)
- `slowfast_r101_pretrained.pth` (241 MB)

## Automatic Download

Models will be automatically downloaded on first use when you run the detection.

## Manual Download

To download models manually:

```bash
cd slowfast_detection
python model_downloader.py
```

## Model Sources

Models are from PyTorchVideo hub:

- SlowFast R50: Trained on Kinetics-400
- SlowFast R101: Trained on Kinetics-400

## Storage Options

Due to the large size of these models (373MB total), they are not included in the Git repository. Options:

1. **Automatic download**: Models download on first use
2. **Git LFS**: Use `git lfs track "*.pth"` to version control large files
3. **External storage**: Host on cloud storage (Google Drive, S3, etc.)
4. **Docker image**: Include models in a Docker image for deployment