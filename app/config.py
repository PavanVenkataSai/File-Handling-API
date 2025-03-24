import os

class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    UPLOAD_DIR = "uploaded_chunks"
    COMPLETED_DIR = "completed_files"
    CLEANUP_INTERVAL_SECONDS = 3600  # 1 hour
    CHUNK_EXPIRY_SECONDS = 7200  # Expire partial uploads after 2 hours

# settings = Settings()

