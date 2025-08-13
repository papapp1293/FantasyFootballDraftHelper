from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .api import analysis, data, dynamic_draft
from .core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fantasy Football Draft Helper API",
    description="API for fantasy football draft analysis and recommendations",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "http://localhost:3001",  # Docker frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(dynamic_draft.router, prefix="/api/dynamic-draft", tags=["dynamic-draft"])

@app.get("/")
async def root():
    return {"message": "Fantasy Football Draft Helper API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
