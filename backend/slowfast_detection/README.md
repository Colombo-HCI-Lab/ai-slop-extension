# SlowFast Framework Integration

## Original Repository

- **Repository**: [facebookresearch/SlowFast](https://github.com/facebookresearch/SlowFast)
- **Authors**: Facebook AI Research (FAIR)
- **License**: Apache License 2.0
- **Paper**: "SlowFast Networks for Video Recognition" (ICCV 2019)

## About SlowFast

SlowFast is a video understanding framework developed by Facebook AI Research that implements dual-pathway architectures
for video recognition. The framework is designed to capture both spatial and temporal information in videos through two
pathways:

### Key Concepts

- **Slow Pathway**: Operates at low frame rates to capture spatial semantics
- **Fast Pathway**: Operates at high frame rates to capture motion/temporal information
- **Lateral Connections**: Enable information exchange between pathways
- **Dual-Speed Processing**: Mimics the human visual system's approach to video understanding

### Supported Architectures

- **SlowFast**: The original dual-pathway architecture (R50, R101 variants)
- **X3D**: Efficient video networks with progressive expansion
- **MViT**: Multiscale Vision Transformers for video recognition
- **I3D**: Inflated 3D ConvNets
- **C2D**: 2D ConvNets with temporal modeling

### Research Impact

- Pioneered dual-pathway video understanding
- State-of-the-art results on Kinetics, AVA, and Charades datasets
- Widely adopted in video analysis research
- Efficient temporal modeling for real-world applications

## Integration in This Repository

### What We've Integrated

We have selectively integrated essential SlowFast components for AI-generated video detection:

```
slowfast_detection/slowfast/
├── models/          # Core model architectures (SlowFast, X3D, MViT)
├── config/          # Configuration system with YACS
├── utils/           # Essential utilities (logging, checkpoints, etc.)
└── datasets/        # Data loading and preprocessing utilities
```

### Key Components Used

1. **Model Architectures** (`models/`):
    - `video_model_builder.py` - Main model construction
    - `resnet_helper.py` - ResNet backbones for SlowFast
    - `head_helper.py` - Classification heads
    - `stem_helper.py` - Input processing stems
    - `build.py` - Model factory functions

2. **Configuration System** (`config/`):
    - `defaults.py` - Default configuration parameters
    - `custom_config.py` - Custom configuration extensions
    - YACS-based configuration management

3. **Utilities** (`utils/`):
    - `logging.py` - Logging utilities
    - `checkpoint.py` - Model checkpoint handling
    - `misc.py` - Miscellaneous helper functions
    - `weight_init_helper.py` - Weight initialization

4. **Data Processing** (`datasets/`):
    - `decoder.py` - Video decoding utilities
    - `transform.py` - Data augmentation and preprocessing
    - `utils.py` - Dataset utilities

### What We've Excluded

- **Training Infrastructure**: Distributed training, optimization, schedulers
- **Evaluation Tools**: Metrics computation, benchmarking scripts
- **Dataset Loaders**: Kinetics, AVA, Charades specific loaders
- **Visualization**: Demo scripts, tensorboard integration
- **Advanced Features**: Multi-grid training, non-local operations

### Model Usage

Instead of cloning the full repository, we now use:

- **PyTorchVideo Hub**: For pre-trained model weights
- **Integrated Architecture**: Direct model construction from our codebase
- **Simplified Interface**: Focused on inference for AI detection

### Configuration

Models are configured through:

```python
from slowfast_detection.slowfast.config import get_cfg
cfg = get_cfg()
cfg.MODEL.ARCH = "slowfast"
cfg.MODEL.MODEL_NAME = "SlowFast"
```

### Benefits of Integration

- **Reduced Dependencies**: No need to clone external repository
- **Focused Functionality**: Only components needed for AI detection
- **Better Maintenance**: Version control over all dependencies
- **Simplified Setup**: One-step installation process
- **Custom Modifications**: Easier to adapt for our specific use case

## License and Attribution

This integration maintains compliance with the Apache License 2.0 from the original SlowFast repository. All original
copyright notices and attributions are preserved in the integrated code.

### Citation

If using SlowFast components in research, please cite:

```bibtex
@inproceedings{feichtenhofer2019slowfast,
  title={Slowfast networks for video recognition},
  author={Feichtenhofer, Christoph and Fan, Haoqi and Malik, Jitendra and He, Kaiming},
  booktitle={Proceedings of the IEEE/CVF International Conference on Computer Vision},
  pages={6202--6211},
  year={2019}
}
```