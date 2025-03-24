import os
import shutil
import aiofiles
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from app.auth import verify_token
from app.models import UploadChunkRequest, FileStatusResponse
from app.config import Settings

router = APIRouter()

UPLOAD_DIR = Settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

file_status = {}

@router.post("/upload_chunk")
async def upload_chunk(chunk_info: UploadChunkRequest, chunk: UploadFile = File(...), _: dict = Depends(verify_token)):
    file_path = os.path.join(UPLOAD_DIR, f"{chunk_info.file_id}.partial")

    async with aiofiles.open(file_path, mode="ab") as f:
        data = await chunk.read()
        if sum(data) % 256 != chunk_info.checksum:
            raise HTTPException(status_code=400, detail="Checksum mismatch")
        await f.write(data)
    
    file_status[chunk_info.file_id] = {
        "received_bytes": chunk_info.end_byte,
        "last_update": time.time()
    }
    return {"message": f"Chunk for {chunk_info.file_id} uploaded."}

@router.get("/download/{file_id}")
async def download_file(file_id: str, request: Request, _: dict = Depends(verify_token)):
    file_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if range_header:
        start, end = parse_range_header(range_header, file_size)
        async def partial_stream():
            with open(file_path, "rb") as f:
                f.seek(start)
                chunk = f.read(end - start + 1)
                yield chunk
        return StreamingResponse(partial_stream(), status_code=206, headers={"Content-Range": f"bytes {start}-{end}/{file_size}"})
    else:
        return StreamingResponse(open(file_path, "rb"))

def parse_range_header(range_header, file_size):
    byte_range = range_header.replace("bytes=", "").split("-")
    start = int(byte_range[0])
    end = int(byte_range[1]) if byte_range[1] else file_size - 1
    return start, end

@router.get("/file_status/{file_id}")
async def get_file_status(file_id: str, _: dict = Depends(verify_token)):
    status_info = file_status.get(file_id)
    if not status_info:
        return FileStatusResponse(
            file_id=file_id, status="pending", received_bytes=0, expected_next_byte=0, completed=False
        )
    file_complete = os.path.exists(os.path.join(UPLOAD_DIR, file_id))
    return FileStatusResponse(
        file_id=file_id,
        status="completed" if file_complete else "partial",
        received_bytes=status_info["received_bytes"],
        expected_next_byte=status_info["received_bytes"] + 1,
        completed=file_complete
    )

async def cleanup_old_chunks():
    now = time.time()
    for file_id, info in list(file_status.items()):
        if now - info["last_update"] > 3600:  # 1 hour timeout
            partial_path = os.path.join(UPLOAD_DIR, f"{file_id}.partial")
            final_path = os.path.join(UPLOAD_DIR, file_id)
            if os.path.exists(partial_path):
                shutil.move(partial_path, final_path)
            file_status.pop(file_id, None)
