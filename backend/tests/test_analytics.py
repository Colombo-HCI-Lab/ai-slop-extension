"""Test analytics API endpoints."""

import pytest
import asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from fastapi.testclient import TestClient

from main import app
from db.models import User, UserPostAnalytics, AnalyticsEvent
from db.session import get_db
from schemas.analytics import UserInitRequest, EventBatchRequest, AnalyticsEvent as EventSchema


class TestAnalyticsAPI:
    """Test analytics API functionality."""

    def test_health_check(self):
        """Test analytics health endpoint."""
        client = TestClient(app)
        response = client.get("/api/v1/analytics/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "analytics"

    @pytest.mark.asyncio
    async def test_user_initialization(self):
        """Test user initialization endpoint."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request_data = {
                "extension_user_id": "test_user_001",
                "browser_info": {"browser": "chrome", "version": "120.0", "userAgent": "Mozilla/5.0 Chrome/120.0"},
                "timezone": "America/New_York",
                "locale": "en_US",
                "client_ip": "127.0.0.1",
            }

            response = await client.post("/api/v1/analytics/users/initialize", json=request_data)

            assert response.status_code == 200
            data = response.json()

            assert "user_id" in data
            assert "session_id" in data
            assert isinstance(data["experiment_groups"], list)

    @pytest.mark.asyncio
    async def test_event_batch_submission(self):
        """Test event batch submission."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # First initialize a user to get session_id
            init_data = {
                "extension_user_id": "test_user_002",
                "browser_info": {"browser": "chrome", "version": "120.0"},
                "timezone": "UTC",
                "locale": "en_US",
            }

            init_response = await client.post("/api/v1/analytics/users/initialize", json=init_data)
            assert init_response.status_code == 200
            session_data = init_response.json()

            # Submit event batch
            events = [
                {
                    "type": "post_view",
                    "category": "interaction",
                    "value": 1.0,
                    "metadata": {"post_id": "12345"},
                    "clientTimestamp": datetime.utcnow().isoformat(),
                },
                {
                    "type": "scroll_behavior",
                    "category": "interaction",
                    "value": 150.5,
                    "metadata": {"direction": "down"},
                    "clientTimestamp": datetime.utcnow().isoformat(),
                },
            ]

            batch_data = {"session_id": session_data["session_id"], "events": events}

            response = await client.post("/api/v1/analytics/events/batch", json=batch_data)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
            assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_post_interaction_tracking(self):
        """Test post interaction tracking."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Initialize user first
            init_data = {
                "extension_user_id": "test_user_003",
                "browser_info": {"browser": "firefox", "version": "119.0"},
                "timezone": "UTC",
                "locale": "en_US",
            }

            init_response = await client.post("/api/v1/analytics/users/initialize", json=init_data)
            user_data = init_response.json()

            # Track post interaction
            post_id = "facebook_post_12345"
            interaction_data = {
                "user_id": user_data["user_id"],
                "interaction_type": "clicked",
                "backend_response_time_ms": 150,
                "time_to_interaction_ms": 2500,
                "reading_time_ms": 8000,
                "scroll_depth_percentage": 75.5,
                "viewport_time_ms": 12000,
            }

            response = await client.post(f"/api/v1/analytics/posts/{post_id}/interactions", json=interaction_data)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "tracked"
            assert "analytics_id" in data

    @pytest.mark.asyncio
    async def test_dashboard_retrieval(self):
        """Test user dashboard retrieval."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Initialize user
            init_data = {
                "extension_user_id": "test_user_004",
                "browser_info": {"browser": "safari", "version": "16.0"},
                "timezone": "UTC",
                "locale": "en_US",
            }

            init_response = await client.post("/api/v1/analytics/users/initialize", json=init_data)
            user_data = init_response.json()

            # Get dashboard data
            date_from = (datetime.utcnow() - timedelta(days=7)).isoformat()
            date_to = datetime.utcnow().isoformat()

            response = await client.get(f"/api/v1/analytics/dashboard/{user_data['user_id']}?date_from={date_from}&date_to={date_to}")

            assert response.status_code == 200
            data = response.json()

            assert data["user_id"] == user_data["user_id"]
            assert "period" in data
            assert "interaction_stats" in data
            assert "session_stats" in data
            assert "chat_stats" in data
            assert "behavior_metrics" in data

    def test_invalid_interaction_type(self):
        """Test validation of interaction types."""
        client = TestClient(app)

        interaction_data = {"user_id": "test_user", "interaction_type": "invalid_type", "backend_response_time_ms": 100}

        response = client.post("/api/v1/analytics/posts/test_post/interactions", json=interaction_data)

        assert response.status_code == 400
        assert "Invalid interaction type" in response.json()["detail"]

    def test_batch_size_validation(self):
        """Test validation of event batch size."""
        client = TestClient(app)

        # Create oversized batch
        events = [
            {"type": "test_event", "category": "test", "clientTimestamp": datetime.utcnow().isoformat()}
        ] * 1001  # Exceed limit of 1000

        batch_data = {"session_id": "test_session", "events": events}

        response = client.post("/api/v1/analytics/events/batch", json=batch_data)

        assert response.status_code == 400
        assert "Batch size exceeds limit" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_performance_metric_recording(self):
        """Test performance metric recording."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            metric_data = {
                "metric_name": "api_response_time",
                "metric_value": 125.5,
                "metric_unit": "ms",
                "endpoint": "/api/v1/posts/analyze",
                "metadata": {"method": "POST", "status_code": 200},
            }

            response = await client.post("/api/v1/analytics/performance/metrics", json=metric_data)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
