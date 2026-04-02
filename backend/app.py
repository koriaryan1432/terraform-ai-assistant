import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

app = FastAPI()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


class TerraformRequest(BaseModel):
    prompt: str
    cloud_provider: str = "aws"


@app.post("/generate")
async def generate_terraform(request: TerraformRequest):
    """Generate Terraform code from natural language"""

    system_prompt = """You are a senior DevOps engineer specialized in Terraform.
Generate production-ready, secure, and well-structured Terraform code.
Follow best practices:
- Use variables for configurable values
- Include proper tags
- Add comments explaining resources
- Use latest stable AWS provider
- Output ONLY the .tf files, no explanations"""

    user_prompt = f"Generate Terraform code for: {request.prompt}"

    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        return {
            "code": response.content[0].text,
            "resources_estimated": len(response.content[0].text.splitlines())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}