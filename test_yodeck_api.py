"""Test script for YoDeck API exploration.

This script helps discover what endpoints are available and what data they return.
Run this to validate the API integration before installing in Home Assistant.

Usage:
    python test_yodeck_api.py YOUR_API_TOKEN_HERE
"""
import asyncio
import json
import sys
from typing import Any

import aiohttp


API_BASE_URL = "https://api.yodeck.com/v1"


class YoDeckAPITester:
    """Test YoDeck API endpoints."""

    def __init__(self, api_token: str):
        """Initialize the tester."""
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    async def test_endpoint(
        self, session: aiohttp.ClientSession, endpoint: str, description: str
    ) -> dict[str, Any]:
        """Test a single endpoint."""
        url = f"{API_BASE_URL}/{endpoint}"
        print(f"\n{'='*80}")
        print(f"Testing: {description}")
        print(f"Endpoint: GET {url}")
        print(f"{'='*80}")

        try:
            async with session.get(url, headers=self.headers) as response:
                print(f"Status Code: {response.status}")
                print(f"Headers: {dict(response.headers)}\n")

                if response.status == 200:
                    data = await response.json()
                    print("Response Data:")
                    print(json.dumps(data, indent=2))
                    return {"success": True, "data": data, "status": response.status}
                elif response.status == 401:
                    print("❌ Authentication failed - check your API token")
                    return {"success": False, "error": "Invalid token", "status": 401}
                elif response.status == 404:
                    print("⚠️  Endpoint not found (might not be available in free tier)")
                    return {"success": False, "error": "Not found", "status": 404}
                elif response.status == 429:
                    retry_after = response.headers.get("Retry-After", "unknown")
                    print(f"⚠️  Rate limited - retry after {retry_after} seconds")
                    return {
                        "success": False,
                        "error": "Rate limited",
                        "status": 429,
                        "retry_after": retry_after,
                    }
                else:
                    text = await response.text()
                    print(f"Error Response: {text}")
                    return {"success": False, "error": text, "status": response.status}

        except Exception as e:
            print(f"❌ Exception: {e}")
            return {"success": False, "error": str(e)}

    async def run_tests(self) -> None:
        """Run all endpoint tests."""
        print("\n" + "="*80)
        print("YoDeck API Endpoint Tester")
        print("="*80)

        async with aiohttp.ClientSession() as session:
            results = {}

            # Test core endpoints
            endpoints = [
                ("screen", "List all screens"),
                ("content", "List all content"),
                ("playlist", "List all playlists"),
                ("schedule", "List all schedules"),
                ("monitor", "Monitor information"),
                ("player", "Player information"),
            ]

            print("\n📋 Testing Core Endpoints...")
            for endpoint, description in endpoints:
                result = await self.test_endpoint(session, endpoint, description)
                results[endpoint] = result
                await asyncio.sleep(1)  # Rate limit friendly

            # If we got screens, test screen-specific endpoints
            if results.get("screen", {}).get("success"):
                screens = results["screen"]["data"]
                if isinstance(screens, list) and len(screens) > 0:
                    screen_id = screens[0].get("id")
                    if screen_id:
                        print("\n\n📱 Testing Screen-Specific Endpoints...")
                        screen_endpoints = [
                            (
                                f"screen/{screen_id}",
                                f"Get details for screen {screen_id}",
                            ),
                            (
                                f"screen/{screen_id}/status",
                                f"Get status for screen {screen_id}",
                            ),
                            (
                                f"screen/{screen_id}/screenshot",
                                f"Get screenshot info for screen {screen_id}",
                            ),
                        ]

                        for endpoint, description in screen_endpoints:
                            result = await self.test_endpoint(
                                session, endpoint, description
                            )
                            results[endpoint] = result
                            await asyncio.sleep(1)

            # Summary
            print("\n\n" + "="*80)
            print("SUMMARY")
            print("="*80)

            successful = [k for k, v in results.items() if v.get("success")]
            failed = [k for k, v in results.items() if not v.get("success")]

            print(f"\n✅ Successful endpoints ({len(successful)}):")
            for endpoint in successful:
                print(f"   - {endpoint}")

            if failed:
                print(f"\n❌ Failed endpoints ({len(failed)}):")
                for endpoint in failed:
                    status = results[endpoint].get("status", "unknown")
                    error = results[endpoint].get("error", "unknown")
                    print(f"   - {endpoint} (Status: {status}, Error: {error})")

            # Recommendations
            print("\n\n📝 RECOMMENDATIONS FOR INTEGRATION:")
            print("-" * 80)

            if "screen" in successful:
                screen_data = results["screen"]["data"]
                if isinstance(screen_data, list) and len(screen_data) > 0:
                    print("\n✅ Screen endpoint works!")
                    print("   Sample screen data fields:")
                    first_screen = screen_data[0]
                    for key in sorted(first_screen.keys()):
                        print(f"   - {key}: {type(first_screen[key]).__name__}")

            if f"screen/{screen_id}/status" in successful:
                status_data = results[f"screen/{screen_id}/status"]["data"]
                print("\n✅ Screen status endpoint works!")
                print("   Sample status data fields:")
                for key in sorted(status_data.keys()):
                    print(f"   - {key}: {type(status_data[key]).__name__}")

            print("\n" + "="*80)


async def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python test_yodeck_api.py YOUR_API_TOKEN")
        print("\nGet your API token from:")
        print("1. Log in to https://yodeck.com")
        print("2. Go to Account > Account Settings > Advanced Settings > API Tokens")
        print("3. Generate a new token and copy it")
        sys.exit(1)

    api_token = sys.argv[1]
    tester = YoDeckAPITester(api_token)
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main())
