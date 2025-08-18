#!/usr/bin/env python3
"""Test script for migrated functionality from NestJS to FastAPI."""

import asyncio
import json
from typing import Any, Dict

import httpx


class TestMigration:
    """Test all migrated endpoints."""

    def __init__(self, base_url: str = "http://localhost:4000"):
        """Initialize test client."""
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_post_id = "test_post_123456"

    async def close(self):
        """Close client."""
        await self.client.aclose()

    def print_result(self, test_name: str, success: bool, response: Any = None):
        """Print test result."""
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n{status}: {test_name}")
        if response:
            print(f"Response: {json.dumps(response, indent=2)[:500]}...")

    async def test_health(self):
        """Test health endpoint."""
        try:
            response = await self.client.get(f"{self.api_url}/health")
            success = response.status_code == 200
            self.print_result("Health Check", success, response.json())
            return success
        except Exception as e:
            self.print_result("Health Check", False, {"error": str(e)})
            return False

    async def test_text_detection(self):
        """Test text content detection."""
        try:
            data = {
                "post_id": self.test_post_id,
                "content": (
                    "In conclusion, it is important to note that this tapestry "
                    "of cutting-edge innovation seamlessly leverages robust solutions "
                    "to navigate the landscape of unprecedented opportunities."
                ),
                "author": "Test User",
                "metadata": {"source": "test"},
            }

            response = await self.client.post(f"{self.api_url}/detect/analyze", json=data)

            success = response.status_code == 200
            result = response.json()

            # Check response structure
            if success:
                success = all(k in result for k in ["post_id", "verdict", "confidence", "explanation"])
                if success:
                    print(f"  Verdict: {result['verdict']}")
                    print(f"  Confidence: {result['confidence']:.2%}")
                    print(f"  Explanation: {result['explanation']}")

            self.print_result("Text Detection", success, result)
            return success
        except Exception as e:
            self.print_result("Text Detection", False, {"error": str(e)})
            return False

    async def test_cache_stats(self):
        """Test cache statistics."""
        try:
            response = await self.client.get(f"{self.api_url}/detect/cache/stats")
            success = response.status_code == 200
            self.print_result("Cache Statistics", success, response.json())
            return success
        except Exception as e:
            self.print_result("Cache Statistics", False, {"error": str(e)})
            return False

    async def test_chat_send(self):
        """Test sending a chat message."""
        try:
            # First ensure we have a post to chat about
            await self.test_text_detection()

            data = {"post_id": self.test_post_id, "message": "Why was this detected as AI-generated content?"}

            response = await self.client.post(f"{self.api_url}/chat/send", json=data)

            success = response.status_code == 200
            result = response.json() if success else None

            if success:
                print(f"  AI Response: {result.get('message', '')[:200]}...")
                print(f"  Suggestions: {result.get('suggested_questions', [])}")

            self.print_result("Chat Send Message", success, result)
            return success
        except Exception as e:
            self.print_result("Chat Send Message", False, {"error": str(e)})
            return False

    async def test_chat_history(self):
        """Test getting chat history."""
        try:
            response = await self.client.get(f"{self.api_url}/chat/history/{self.test_post_id}")

            success = response.status_code == 200
            result = response.json() if success else None

            if success:
                print(f"  Total messages: {result.get('total_messages', 0)}")

            self.print_result("Chat History", success, result)
            return success
        except Exception as e:
            self.print_result("Chat History", False, {"error": str(e)})
            return False

    async def test_get_post(self):
        """Test getting a specific post."""
        try:
            response = await self.client.get(f"{self.api_url}/posts/{self.test_post_id}")

            success = response.status_code == 200
            result = response.json() if success else None

            if success:
                print(f"  Post ID: {result.get('post_id')}")
                print(f"  Verdict: {result.get('verdict')}")
                print(f"  Author: {result.get('author')}")

            self.print_result("Get Post", success, result)
            return success
        except Exception as e:
            self.print_result("Get Post", False, {"error": str(e)})
            return False

    async def test_list_posts(self):
        """Test listing posts."""
        try:
            response = await self.client.get(f"{self.api_url}/posts", params={"limit": 5})

            success = response.status_code == 200
            result = response.json() if success else None

            if success:
                print(f"  Total posts: {result.get('total', 0)}")
                print(f"  Posts returned: {len(result.get('posts', []))}")

            self.print_result("List Posts", success, result)
            return success
        except Exception as e:
            self.print_result("List Posts", False, {"error": str(e)})
            return False

    async def test_update_post(self):
        """Test updating a post."""
        try:
            data = {"confidence": 0.95, "explanation": "Updated explanation from test"}

            response = await self.client.put(f"{self.api_url}/posts/{self.test_post_id}", json=data)

            success = response.status_code == 200
            result = response.json() if success else None

            if success:
                print(f"  Updated confidence: {result.get('confidence')}")
                print(f"  Updated explanation: {result.get('explanation')}")

            self.print_result("Update Post", success, result)
            return success
        except Exception as e:
            self.print_result("Update Post", False, {"error": str(e)})
            return False

    async def test_suggested_questions(self):
        """Test getting suggested questions."""
        try:
            response = await self.client.get(f"{self.api_url}/chat/suggestions/{self.test_post_id}")

            success = response.status_code == 200
            result = response.json() if success else None

            if success and isinstance(result, list):
                print(f"  Suggestions: {result[:3]}")

            self.print_result("Suggested Questions", success, result)
            return success
        except Exception as e:
            self.print_result("Suggested Questions", False, {"error": str(e)})
            return False

    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("Testing Migrated NestJS -> FastAPI Functionality")
        print("=" * 60)

        tests = [
            ("Health Check", self.test_health),
            ("Text Detection", self.test_text_detection),
            ("Cache Statistics", self.test_cache_stats),
            ("Chat Send", self.test_chat_send),
            ("Chat History", self.test_chat_history),
            ("Get Post", self.test_get_post),
            ("List Posts", self.test_list_posts),
            ("Update Post", self.test_update_post),
            ("Suggested Questions", self.test_suggested_questions),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\nRunning: {test_name}")
            print("-" * 40)
            success = await test_func()
            results.append((test_name, success))

        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, success in results if success)
        total = len(results)

        for test_name, success in results:
            status = "✅" if success else "❌"
            print(f"{status} {test_name}")

        print(f"\nTotal: {passed}/{total} tests passed")

        if passed == total:
            print("\n🎉 All tests passed! Migration successful!")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")

        return passed == total


async def main():
    """Main test runner."""
    tester = TestMigration()
    try:
        # Check if server is running
        try:
            response = await tester.client.get(f"{tester.base_url}/")
            print(f"Server is running at {tester.base_url}")
        except:
            print(f"⚠️  Server not running at {tester.base_url}")
            print("Please start the server with: uv run python -m uvicorn main:app --port 4000")
            return

        success = await tester.run_all_tests()
        exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
