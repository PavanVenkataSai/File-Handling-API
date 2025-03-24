# File Handling REST API

## Features:
- Chunked file upload and resumable uploads
- Partial file downloads via Content-Range
- File status monitoring API
- Secure authentication using JWT tokens
- Background cleanup (can be added as future enhancement)

## Setup:
1. Create a virtual environment and install dependencies:
```bash
pip install -r requirements.txt
```
2. Start the server:
```bash
uvicorn main:app --reload
```
3. Use Swagger UI at `http://localhost:8000/docs`

**Authorization:**
Use JWT token for API access. Generate using `create_access_token()` in `auth.py`.
