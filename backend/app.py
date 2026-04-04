from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
import re
import json
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from groq import Groq, GroqError
from fastapi.middleware.cors import CORSMiddleware

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("terraform-ai-assistant")

load_dotenv()

# Rate limiter: 10 requests per minute per IP
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Terraform AI Assistant", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup validation
if not os.getenv("GROQ_API_KEY"):
    logger.warning("GROQ_API_KEY not found in .env file - application may fail")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class TerraformRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=1000, description="Natural language description of infrastructure")
    cloud_provider: str = Field("aws", pattern="^(aws|azure|gcp|kubernetes)$")

    @field_validator('prompt')
    @classmethod
    def validate_and_sanitize_prompt(cls, v: str) -> str:
        """Sanitize prompt to prevent injection attacks"""
        # Remove excessive whitespace
        v = ' '.join(v.split())

        # Check for suspicious patterns (basic prompt injection detection)
        suspicious_patterns = [
            r'```\s*hcl',
            r'terraform\s*{',
            r'provider\s*"',
            r'resource\s*"',
            r'```',
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(f"Prompt contains forbidden Terraform syntax")

        # Length check (already enforced by Field, but double-check)
        if len(v) < 5:
            raise ValueError("Prompt must be at least 5 characters long")

        if len(v) > 1000:
            raise ValueError("Prompt must be less than 1000 characters")

        return v.strip()

class TerraformResponse(BaseModel):
    success: bool
    code: str
    lines_of_code: int
    cloud_provider: str

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses"""
    start_time = datetime.now(timezone.utc)

    # Generate request ID for tracing
    request_id = f"{start_time.strftime('%Y%m%d-%H%M%S')}-{id(request)}"

    # Log request
    logger.info(
        "Request received",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": get_remote_address(request),
            "user_agent": request.headers.get("user-agent", "unknown")
        }
    )

    try:
        response = await call_next(request)

        # Log response
        process_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "response_time_ms": round(process_time * 1000, 2)
            }
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as e:
        logger.error(
            "Request failed",
            extra={
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "service": "terraform-ai-assistant",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/generate", response_model=TerraformResponse)
@limiter.limit("10/minute")
async def generate_terraform(request: Request, terraform_request: TerraformRequest):
    """
    Generate Terraform code from natural language description.
    Rate limited to 10 requests per minute per IP.
    """
    logger.info(
        "Generating Terraform code",
        extra={
            "cloud_provider": terraform_request.cloud_provider,
            "prompt_length": len(terraform_request.prompt)
        }
    )

    system_prompt = """You are an expert DevOps engineer and Terraform specialist.
YOUR TASK:
- Generate ONLY valid, production-ready Terraform code
- NEVER include explanations, markdown, or conversational text
- Output ONLY raw .tf file content
MANDATORY REQUIREMENTS:
1. Start with terraform block specifying provider version
2. Use variables for all configurable values (region, instance types, CIDR blocks)
3. Add comprehensive tags to all resources
4. Include output blocks for important values
5. Follow AWS Well-Architected Framework security best practices
6. Use proper HCL syntax with 2-space indentation
7. Separate resources with blank lines
EXAMPLE STRUCTURE:
terraform { required_providers { aws = { source="hashicorp/aws"; version="~> 5.0" } } }
variable "aws_region" { description="AWS region"; type=string; default="us-east-1" }
provider "aws" { region = var.aws_region }
# Your resources here
output "vpc_id" { description="ID of the VPC"; value=aws_vpc.main.id }
If the request is ambiguous, make reasonable assumptions and document in comments."""

    user_prompt = f"Generate production-ready Terraform code for: {terraform_request.prompt}"

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=4000,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        terraform_code = response.choices[0].message.content

        # Clean markdown code blocks if present
        if "```" in terraform_code:
            matches = re.findall(r'```(?:hcl|terraform|tf)?\n([\s\S]*?)```', terraform_code)
            if matches:
                terraform_code = matches[0].strip()

        # Validate we got some code
        if not terraform_code or len(terraform_code.strip()) == 0:
            raise ValueError("AI returned empty code")

        lines_of_code = len(terraform_code.splitlines())

        logger.info(
            "Terraform code generated successfully",
            extra={
                "lines_of_code": lines_of_code,
                "code_length": len(terraform_code)
            }
        )

        return TerraformResponse(
            success=True,
            code=terraform_code,
            lines_of_code=lines_of_code,
            cloud_provider=terraform_request.cloud_provider
        )

    except GroqError as e:
        logger.error(
            "Groq API error",
            extra={
                "error": str(e),
                "status_code": getattr(e, 'status_code', 'unknown'),
                "error_type": "groq_error"
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=502,
            detail=f"AI service error: {str(e)}"
        )

    except ValueError as e:
        logger.error(
            "Validation error",
            extra={"error": str(e), "error_type": "validation_error"}
        )
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )

    except Exception as e:
        logger.error(
            "Unexpected error generating Terraform",
            extra={"error": str(e), "error_type": "unexpected"},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Terraform code: An unexpected error occurred"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)