import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules.youtube_uploader import upload_video
from api.deps import log_progress
from api.routers.shorts import calculate_render_percentage

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

class YouTubeUploadRequest(BaseModel):
    """Parameters required to upload a rendered Short to YouTube."""
    video_path: str = Field(..., description="Absolute path to the rendered video file")
    title: str = Field(..., description="Title for the YouTube Short (max 100 chars)")
    description: str = Field(..., description="Description for the YouTube Short")
    keywords: str = Field("", description="Optional comma-separated tags")
    channel_name: Optional[str] = Field(None, description="Active channel name for isolated credentials")

@router.post("/upload")
def upload_to_youtube(req: YouTubeUploadRequest):
    """
    Upload a rendered Short to YouTube.
    - Validates that `video_path` exists.
    - Calls `modules.youtube_uploader.upload_video`.
    - Transmits SSE progress to update the UI progress bar.
    - Returns the YouTube video ID on success.
    """
    if not os.path.isfile(req.video_path):
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found at path: {req.video_path}"
        )

    channel_name = req.channel_name or "default"
    log_progress(channel_name, "🚀 Iniciando subida del Short a YouTube...", "#FFD700", percentage=2)

    def sse_status_callback(msg: str, color: str = "#FFD700"):
        perc = calculate_render_percentage(msg)
        log_progress(channel_name, msg, color, percentage=perc)

    success, result = upload_video(
        file_path=req.video_path,
        title=req.title,
        description=req.description,
        keywords=req.keywords,
        channel_name=req.channel_name,
        status_callback=sse_status_callback
    )
    if not success:
        log_progress(channel_name, f"❌ Fallo en la subida a YouTube: {result}", "#ff1a1a", percentage=0)
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {result}")

    log_progress(channel_name, f"🎉 ¡Short publicado con éxito en YouTube! (ID: {result})", "#00ff00", percentage=100)
    return {"status": "success", "video_id": result}
