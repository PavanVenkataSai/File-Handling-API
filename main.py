from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.auth import verify_token,create_access_token
from app.models import FileStatus, file_status_db
import os
import shutil
import aiofiles
from datetime import datetime, timedelta
import hashlib
import uvicorn

app = FastAPI(title="File Handling REST API")

# CORS setup if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
CHUNK_DIR = "partial_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)

# Utility function to save chunks
async def save_chunk(file_id, chunk: UploadFile, start_byte: int, end_byte: int):
    partial_file_path = os.path.join(CHUNK_DIR, f"{file_id}.part")
    async with aiofiles.open(partial_file_path, "ab") as out_file:
        content = await chunk.read()
        await out_file.write(content)

    # Update file status
    file_status_db[file_id] = FileStatus(
        file_id=file_id,
        last_updated=datetime.utcnow(),
        received_end_byte=end_byte,
        status="partial"
    )

# Endpoint to upload file chunks
@app.post("/upload")
async def upload_chunk(
    request: Request,
    file_id: str,
    start_byte: int,
    end_byte: int,
    chunk: UploadFile = File(...),
    current_user=Depends(verify_token),
):
    await save_chunk(file_id, chunk, start_byte, end_byte)
    print(chunk.filename)

    # If this is the last chunk, move file to completed uploads
    if chunk.filename.endswith(".end"):
        partial_file_path = os.path.join(CHUNK_DIR, f"{file_id}.part")
        completed_path = os.path.join(UPLOAD_DIR, f"{file_id}.bin")
        shutil.move(partial_file_path, completed_path)
        file_status_db[file_id].status = "complete"

    return {"message": "Chunk received successfully"}

# Partial file download endpoint
@app.get("/download/{file_id}")
async def partial_download(
    file_id: str,
    range_header: str = None,
    current_user=Depends(verify_token),
):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.bin")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(file_path)

    if range_header:
        start, end = range_header.replace("bytes=", "").split("-")
        start = int(start)
        end = int(end) if end else file_size - 1
    else:
        start, end = 0, file_size - 1

    async def iter_file():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            chunk_size = 1024 * 1024
            while remaining > 0:
                read_bytes = f.read(min(chunk_size, remaining))
                if not read_bytes:
                    break
                remaining -= len(read_bytes)
                yield read_bytes

    headers = {"Content-Range": f"bytes {start}-{end}/{file_size}"}
    return StreamingResponse(iter_file(), headers=headers, status_code=206)

# Check file status
@app.get("/status/{file_id}")
async def check_file_status(file_id: str, current_user=Depends(verify_token)):
    status_obj = file_status_db.get(file_id)
    if not status_obj:
        return {"file_id": file_id, "status": "not found"}

    return {
        "file_id": file_id,
        "status": status_obj.status,
        "received_end_byte": status_obj.received_end_byte,
        "last_updated": status_obj.last_updated.isoformat(),
    }

# Background cleanup process
@app.on_event("startup")
async def cleanup_scheduler():
    from asyncio import create_task, sleep

    async def cleanup_task():
        while True:
            now = datetime.utcnow()
            threshold = timedelta(minutes=30)
            to_remove = []
            for file_id, status in file_status_db.items():
                if (
                    status.status == "partial"
                    and (now - status.last_updated) > threshold
                ):
                    partial_path = os.path.join(CHUNK_DIR, f"{file_id}.part")
                    if os.path.exists(partial_path):
                        completed_path = os.path.join(UPLOAD_DIR, f"{file_id}.bin")
                        shutil.move(partial_path, completed_path)
                        status.status = "stale_saved"
                        print(f"Stale partial file {file_id} saved as complete.")
            await sleep(600)  # Check every 10 minutes

    create_task(cleanup_task())

# Token generation (testing endpoint)
@app.get("/generate-token")
async def generate_token():
    token = create_access_token({"device_id": "test_device"})
    return {"access_token": token}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
