import io

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_ok(client: TestClient):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "gpu_available" in data


def test_image_models_ok(client: TestClient):
    res = client.get("/api/v1/image/models")
    assert res.status_code == 200
    data = res.json()
    assert "image_models" in data
    assert "default_image_model" in data


def test_image_detect_rejects_unsupported_extension(client: TestClient):
    payload = {"file": ("foo.txt", b"not-an-image", "text/plain")}
    res = client.post("/api/v1/image/detect", files=payload)
    assert res.status_code == 400
    assert "Unsupported file format" in res.text


def test_video_models_ok(client: TestClient):
    res = client.get("/api/v1/video/models")
    assert res.status_code == 200
    models = res.json()
    assert isinstance(models, list)
    assert all({"name", "description", "is_default", "supported_formats"} <= set(m.keys()) for m in models)


def test_video_detect_rejects_unsupported_extension(client: TestClient):
    # Upload a .txt pretending to be a video should fail fast
    files = {"file": ("video.txt", b"noop", "text/plain")}
    res = client.post("/api/v1/video/detect", files=files)
    assert res.status_code in (400, 422)


def test_removed_image_url_endpoint_returns_404(client: TestClient):
    res = client.post("/api/v1/image/detect-url", json={"image_url": "http://example.com/a.jpg"})
    assert res.status_code == 404


def test_removed_video_url_endpoint_returns_404(client: TestClient):
    res = client.post("/api/v1/video/detect-url", json={"video_url": "http://example.com/a.mp4"})
    assert res.status_code == 404
