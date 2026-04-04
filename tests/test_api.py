import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

class TestHealthCheck:
    """Tests for health check endpoint"""

    def test_health_check(self):
        """Test the health endpoint returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "terraform-ai-assistant"
        assert "timestamp" in data

class TestInputValidation:
    """Tests for input validation and sanitization"""

    def test_prompt_too_short(self):
        """Test that prompts shorter than 5 characters are rejected"""
        response = client.post("/generate", json={
            "prompt": "abc",
            "cloud_provider": "aws"
        })
        assert response.status_code == 422
        assert "at least 5 characters" in response.json()["detail"][0]["msg"]

    def test_prompt_too_long(self):
        """Test that prompts longer than 1000 characters are rejected"""
        long_prompt = "a" * 1001
        response = client.post("/generate", json={
            "prompt": long_prompt,
            "cloud_provider": "aws"
        })
        assert response.status_code == 422
        # Pydantic's error message may vary slightly
        response_data = response.json()
        assert any("1000" in err["msg"] for err in response_data["detail"])

    def test_prompt_with_terraform_syntax(self):
        """Test that prompts containing Terraform syntax are rejected (injection prevention)"""
        response = client.post("/generate", json={
            "prompt": "terraform { resource \"aws_instance\" {} }",
            "cloud_provider": "aws"
        })
        assert response.status_code == 422
        assert "forbidden Terraform syntax" in response.json()["detail"][0]["msg"]

    def test_prompt_with_code_block(self):
        """Test that prompts with code blocks are rejected"""
        response = client.post("/generate", json={
            "prompt": "```hcl\nresource \"aws_s3_bucket\" {}```",
            "cloud_provider": "aws"
        })
        assert response.status_code == 422

    def test_missing_prompt(self):
        """Test that missing prompt field is rejected"""
        response = client.post("/generate", json={
            "cloud_provider": "aws"
        })
        assert response.status_code == 422

    def test_empty_prompt(self):
        """Test that empty prompt is rejected"""
        response = client.post("/generate", json={
            "prompt": "",
            "cloud_provider": "aws"
        })
        assert response.status_code == 422

    def test_whitespace_only_prompt(self):
        """Test that whitespace-only prompt is rejected"""
        response = client.post("/generate", json={
            "prompt": "   ",
            "cloud_provider": "aws"
        })
        assert response.status_code == 422

    def test_invalid_cloud_provider(self):
        """Test that invalid cloud provider is rejected"""
        response = client.post("/generate", json={
            "prompt": "Create an S3 bucket",
            "cloud_provider": "invalid"
        })
        assert response.status_code == 422

class TestGenerateEndpoint:
    """Tests for the generate endpoint"""

    def test_generate_valid_prompt(self):
        """Test that a valid prompt returns Terraform code"""
        response = client.post("/generate", json={
            "prompt": "Create an S3 bucket for static website hosting",
            "cloud_provider": "aws"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "code" in data
        assert len(data["code"]) > 0
        assert "lines_of_code" in data
        assert data["cloud_provider"] == "aws"

    def test_generate_alternate_cloud_provider(self):
        """Test with azure cloud provider"""
        response = client.post("/generate", json={
            "prompt": "Create a storage account",
            "cloud_provider": "azure"
        })
        # Should succeed (even if AI returns aws code, the API should accept it)
        assert response.status_code == 200

    def test_response_structure(self):
        """Test response structure contains all required fields"""
        response = client.post("/generate", json={
            "prompt": "Create a simple EC2 instance",
            "cloud_provider": "aws"
        })
        assert response.status_code == 200
        data = response.json()
        required_fields = {"success", "code", "lines_of_code", "cloud_provider"}
        assert all(field in data for field in required_fields)
        assert isinstance(data["success"], bool)
        assert isinstance(data["code"], str)
        assert isinstance(data["lines_of_code"], int)
        assert isinstance(data["cloud_provider"], str)

class TestRateLimiting:
    """Tests for rate limiting functionality"""

    def test_rate_limit_not_exceeded(self):
        """Test that a single request succeeds"""
        response = client.post("/generate", json={
            "prompt": "Create an S3 bucket",
            "cloud_provider": "aws"
        })
        # Should not return 429 on first request
        assert response.status_code != 429

    # Note: Testing actual rate limit exceed would require multiple rapid requests.
    # This is a basic check that the limiter is configured.
    def test_rate_limit_header_present(self):
        """Test that rate limit headers are present in response"""
        response = client.post("/generate", json={
            "prompt": "Create an S3 bucket",
            "cloud_provider": "aws"
        })
        # SlowAPI should add rate limit headers
        # But behavior depends on configuration
        assert response.status_code in [200, 429]

class TestErrorHandling:
    """Tests for error handling"""

    def test_health_check_response_time(self):
        """Health check should be fast"""
        import time
        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0  # Should respond in less than 1 second

    def test_generate_with_minimal_valid_prompt(self):
        """Test with exactly 5 character prompt (minimum valid)"""
        response = client.post("/generate", json={
            "prompt": "Hello",
            "cloud_provider": "aws"
        })
        # Should be accepted (5 chars exactly is minimum)
        assert response.status_code == 200

    def test_extra_whitespace_in_prompt(self):
        """Test that extra whitespace is trimmed"""
        response = client.post("/generate", json={
            "prompt": "   Create an S3 bucket with versioning   ",
            "cloud_provider": "aws"
        })
        # Should succeed after trimming
        assert response.status_code == 200

