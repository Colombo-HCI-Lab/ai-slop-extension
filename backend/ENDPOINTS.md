# API Endpoints Documentation

This document describes all the audio and video endpoints available in the AI Content Detection API. The API provides comprehensive functionality for detecting AI-generated content in both videos and images using state-of-the-art models.

## Base URL

```
http://localhost:4001/api/v1
```

## Authentication

Currently, no authentication is required for accessing the endpoints.

---

## Health & System Endpoints

### Health Check
**GET** `/health`

Health check endpoint that returns system status including GPU availability and disk space.

**Response Schema:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "models_loaded": ["slowfast_r50"],
  "gpu_available": true,
  "disk_space_mb": 15360.5
}
```

**Example:**
```bash
curl "http://localhost:4001/api/v1/health"
```

---

## Video Detection Endpoints

### Get Available Video Models
**GET** `/video/models`

Returns information about all available SlowFast models for video detection.

**Response:**
```json
[
  {
    "name": "slowfast_r50",
    "description": "SlowFast SLOWFAST_R50 model for video classification",
    "is_default": true,
    "supported_formats": [".mp4", ".avi", ".mov", ".webm"]
  },
  {
    "name": "slowfast_r101",
    "description": "SlowFast SLOWFAST_R101 model for video classification",
    "is_default": false,
    "supported_formats": [".mp4", ".avi", ".mov", ".webm"]
  }
]
```

**Example:**
```bash
curl "http://localhost:4001/api/v1/video/models"
```

### Video Upload Detection
**POST** `/video/detect`

Upload and analyze a video file for AI generation detection.

**Request Parameters:**
- `file` (file, required): Video file to analyze (MP4, AVI, MOV, WebM)
- `model_name` (form field, optional): Model to use for detection
  - Default: `slowfast_r50`
  - Options: `slowfast_r50`, `slowfast_r101`, `x3d_m`
- `threshold` (form field, optional): Detection threshold for AI classification (0.0-1.0)
  - Default: `0.5`

**Response Schema:**
```json
{
  "status": "completed",
  "video_info": {
    "filename": "sample_video.mp4",
    "duration": 10.5,
    "fps": 30.0,
    "resolution": "1920x1080",
    "file_size": 15728640
  },
  "detection_result": {
    "is_ai_generated": false,
    "confidence": 0.85,
    "model_used": "slowfast_r50",
    "processing_time": 2.34,
    "top_predictions": [
      {
        "class_name": "real_video",
        "probability": 0.85,
        "class_index": 0
      },
      {
        "class_name": "ai_generated",
        "probability": 0.15,
        "class_index": 1
      }
    ]
  },
  "created_at": "2024-01-15T10:30:00.123456"
}
```

**Example:**
```bash
curl -X POST "http://localhost:4001/api/v1/video/detect" \
  -F "file=@sample_video.mp4" \
  -F "model_name=slowfast_r50" \
  -F "threshold=0.5"
```

### Video URL Detection
**POST** `/video/detect-url`

Download and analyze a video from URL for AI generation detection.

**Request Body:**
```json
{
  "video_url": "https://example.com/video.mp4",
  "model_name": "slowfast_r50",
  "threshold": 0.5
}
```

**Request Schema:**
- `video_url` (string, required): Public URL of the video to analyze (HTTP/HTTPS only)
- `model_name` (string, optional): Model to use for detection
  - Default: `slowfast_r50`
  - Options: `slowfast_r50`, `slowfast_r101`, `x3d_m`
- `threshold` (number, optional): Detection threshold for AI classification (0.0-1.0)
  - Default: `0.5`

**Response:** Same as Video Upload Detection

**Example:**
```bash
curl -X POST "http://localhost:4001/api/v1/video/detect-url" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/sample.mp4",
    "model_name": "slowfast_r50",
    "threshold": 0.5
  }'
```

---

## Image Detection Endpoints

### Get Available Image Models
**GET** `/image/models`

Returns information about all available image detection models.

**Response Schema:**
```json
{
  "image_models": [
    "auto",
    "openclip_vit_l14",
    "openclip_vit_b32",
    "openclip_eva02_l14",
    "clipbased"
  ],
  "default_image_model": "auto"
}
```

**Example:**
```bash
curl "http://localhost:4001/api/v1/image/models"
```

### Image Upload Detection
**POST** `/image/detect`

Upload and analyze an image file for AI generation detection.

**Request Parameters:**
- `file` (file, required): Image file to analyze (JPEG, PNG, BMP, TIFF, WebP)
- `model_name` (form field, optional): Model to use for detection
  - Default: `auto`
  - Options: `auto`, `ssp`, `clipbased`, OpenCLIP variants
- `threshold` (form field, optional): Detection threshold
  - Default: `0.0` (model-specific)

**Response Schema:**
```json
{
  "status": "completed",
  "image_info": {
    "filename": "sample_image.jpg",
    "size": "1920x1080",
    "format": "image/jpeg",
    "file_size": 524288
  },
  "detection_result": {
    "is_ai_generated": true,
    "confidence": 0.92,
    "model_used": "clipbased",
    "processing_time": 0.45,
    "llr_score": 2.34,
    "probability": 0.92,
    "threshold": 0.0,
    "metadata": {
      "image_size": "1920x1080",
      "model_variant": "openclip_vit_l14"
    }
  },
  "created_at": "2024-01-15T10:30:00.123456",
  "completed_at": "2024-01-15T10:30:00.568910"
}
```

**Example:**
```bash
curl -X POST "http://localhost:4001/api/v1/image/detect" \
  -F "file=@sample_image.jpg" \
  -F "model_name=auto" \
  -F "threshold=0.0"
```

### Image URL Detection
**POST** `/image/detect-url`

Analyze an image from URL for AI generation detection.

**Request Body:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "model_name": "auto",
  "threshold": 0.0
}
```

**Request Schema:**
- `image_url` (string, required): URL of the image to analyze
- `model_name` (string, optional): Model to use for detection
  - Default: `auto`
  - Options: `auto`, `ssp`, `clipbased`, OpenCLIP variants
- `threshold` (number, optional): Detection threshold
  - Default: `0.0` (model-specific)

**Response:** Same as Image Upload Detection

**Example:**
```bash
curl -X POST "http://localhost:4001/api/v1/image/detect-url" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "model_name": "auto",
    "threshold": 0.0
  }'
```

---

## Model Information

### Available Video Models

| Model | Description | Accuracy | Speed | Default |
|-------|-------------|----------|-------|---------|
| `slowfast_r50` | SlowFast ResNet-50 backbone | Good | Fast | ✓ |
| `slowfast_r101` | SlowFast ResNet-101 backbone | Higher | Slower | |
| `x3d_m` | Efficient 3D CNN model | Good | Very Fast | |

### Available Image Models

| Model | Description | Method | Default |
|-------|-------------|--------|---------|
| `auto` | Automatic model selection | ClipBased (primary) | ✓ |
| `clipbased` | CLIP-based detection | OpenCLIP variants | |
| `openclip_vit_l14` | Vision Transformer Large | CLIP + LLR scoring | |
| `openclip_vit_b32` | Vision Transformer Base | CLIP + LLR scoring | |
| `openclip_eva02_l14` | EVA02 Large model | CLIP + LLR scoring | |
| `ssp` | SSP-based detector | Statistical analysis | |

---

## Error Responses

### Common Error Codes

- **400 Bad Request**: Invalid file format, file too large, or invalid parameters
- **422 Unprocessable Entity**: Request validation errors
- **500 Internal Server Error**: Processing failures or model errors

### Error Response Schema

```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "status_code": 422,
  "detail": "Additional error details (debug mode only)"
}
```

### Validation Error Schema

```json
{
  "errors": [
    {
      "loc": ["field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## File Size and Format Limits

### Video Files
- **Supported Formats**: MP4, AVI, MOV, WebM
- **Maximum File Size**: Configurable (default: varies by deployment)
- **Supported Codecs**: H.264, H.265, VP8, VP9

### Image Files
- **Supported Formats**: JPEG, PNG, BMP, TIFF, WebP
- **Maximum File Size**: 10MB (default)
- **Supported MIME Types**: `image/jpeg`, `image/png`, `image/bmp`, `image/tiff`, `image/webp`

---

## Response Times

| Endpoint | Typical Response Time |
|----------|----------------------|
| Health Check | < 100ms |
| Video Models | < 50ms |
| Image Models | < 50ms |
| Video Detection (upload) | 2-10 seconds |
| Video Detection (URL) | 3-15 seconds |
| Image Detection (upload) | 0.2-2 seconds |
| Image Detection (URL) | 0.5-3 seconds |

*Response times vary based on file size, model complexity, and hardware capabilities.*

---

## Notes

1. **GPU Acceleration**: When available, models automatically use GPU acceleration for faster processing
2. **Model Loading**: Models are loaded on-demand and cached for subsequent requests
3. **File Cleanup**: Uploaded files are automatically cleaned up after processing
4. **Async Processing**: All detection endpoints support asynchronous processing
5. **Batch Processing**: Image detection supports batch processing for multiple images
6. **URL Validation**: URL endpoints validate URLs and support HTTP/HTTPS protocols only
7. **Debug Mode**: When debug mode is enabled, detailed error information is included in responses
8. **CORS**: Cross-Origin Resource Sharing is enabled for web applications

---

## Testing

Test the API using the provided test scripts:

```bash
# Test video detection
python test_slowfast.py

# Test image detection  
python test_clipbased.py

# Quick tests
python test_slowfast.py --quick
python test_clipbased.py --quick
```

For interactive API documentation, visit:
- Swagger UI: `http://localhost:4001/docs` (debug mode only)
- ReDoc: `http://localhost:4001/redoc` (debug mode only)