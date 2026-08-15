import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules.youtube_uploader import upload_video

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

class YouTubeUploadRequest(BaseModel):
    """Parameters required to upload a rendered Short to YouTube."""
    video_path: str = Field(..., description="Absolute path to the rendered video file")
    title: str = Field(..., description="Title for the YouTube Short (max 100 chars)")
    description: str = Field(..., description="Description for the YouTube Short")
    keywords: str = Field("", description="Optional comma-separated tags")

@router.post("/upload")
def upload_to_youtube(req: YouTubeUploadRequest):
    """
    Upload a rendered Short to YouTube.
    - Validates that `video_path` exists.
    - Calls `modules.youtube_uploader.upload_video`.
    - Returns the YouTube video ID on success.
    """
    if not os.path.isfile(req.video_path):
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found at path: {req.video_path}"
        )

    success, result = upload_video(
        file_path=req.video_path,
        title=req.title,
        description=req.description,
        keywords=req.keywords,
        status_callback=None
    )
    if not success:
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {result}")

    return {"status": "success", "video_id": result}
