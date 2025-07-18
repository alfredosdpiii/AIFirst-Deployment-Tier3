import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from google.cloud import secretmanager
import json
import shopsage_core as ss

# Pydantic models
class ShoppingQuery(BaseModel):
    question: str = Field(..., description="Shopping question or comparison query")

class ProductInfo(BaseModel):
    title: str
    url: str
    snippet: str
    summary: Optional[str] = None

class ShoppingRecommendation(BaseModel):
    query: str
    winner: str
    ranking: List[str]
    reasons: List[str]
    sources: List[Dict]

# Function to load secrets from GCP Secret Manager
def load_secret(secret_id: str, project_id: str = None) -> str:
    """Load secret from GCP Secret Manager"""
    if project_id is None:
        project_id = os.getenv("GCP_PROJECT_ID", "your-project-id")
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error loading secret {secret_id}: {e}")
        # Fallback to environment variable
        return os.getenv(secret_id, "")

# Load API keys based on environment
IS_CLOUD_RUN = os.getenv("K_SERVICE") is not None

if IS_CLOUD_RUN:
    # Running on Cloud Run - use Secret Manager
    os.environ["TAVILY_API_KEY"] = load_secret("TAVILY_API_KEY")
    os.environ["OPENAI_API_KEY"] = load_secret("OPENAI_API_KEY")
else:
    # Local development - use .env file
    from dotenv import load_dotenv
    load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="ShopSage API - Cloud Run",
    description="AI-powered shopping recommendation system optimized for Google Cloud Run",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "ShopSage API",
        "version": "2.0.0",
        "platform": "Google Cloud Run",
        "description": "AI-powered shopping recommendations",
        "endpoints": {
            "POST /recommend": "Get shopping recommendations",
            "GET /health": "Health check endpoint",
            "GET /docs": "Interactive API documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "service": "ShopSage API",
        "platform": "Cloud Run",
        "region": os.getenv("K_SERVICE_REGION", "unknown")
    }

@app.post("/recommend", response_model=ShoppingRecommendation)
async def recommend(query: ShoppingQuery):
    """
    Get shopping recommendations based on user query
    
    This endpoint:
    1. Searches for products using Tavily API
    2. Analyzes products using AI
    3. Returns recommendations with ranking and reasoning
    """
    try:
        # Create ShopSage instance
        sage = ss.ShopSage()
        
        # Run the recommendation pipeline
        result = sage.run_pipeline(query.question)
        
        return ShoppingRecommendation(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/search")
async def search_products(query: str, max_results: int = 8):
    """
    Search for products without analysis
    
    Useful for getting raw search results from Tavily
    """
    try:
        scout = ss.ScoutAgent()
        results = scout.search(query, max_results)
        return {"query": query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_products(products: List[Dict], question: str):
    """
    Analyze and rank already retrieved products
    
    Useful when you have product data from another source
    """
    try:
        judge = ss.JudgeAgent()
        verdict = judge.judge_products(question, products)
        return verdict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Cloud Run specific endpoint
@app.get("/_ah/warmup")
async def warmup():
    """Warmup endpoint for Cloud Run to reduce cold starts"""
    # Perform any initialization here
    return {"status": "warmed up"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)