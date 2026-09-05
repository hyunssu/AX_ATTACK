import io
import uuid
from datetime import timedelta

from minio import Minio

from backend_app.config import BUCKET_NAME, MINIO_EXT_ENDPOINT, MINIO_PASSWORD, MINIO_USER

minio_client = Minio(
    MINIO_EXT_ENDPOINT,
    access_key=MINIO_USER,
    secret_key=MINIO_PASSWORD,
    secure=False
)


def upload_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    unique_filename = f"{uuid.uuid4()}_{filename}"
    minio_client.put_object(
        BUCKET_NAME, unique_filename, io.BytesIO(file_bytes), len(file_bytes), content_type=content_type
    )
    return minio_client.get_presigned_url("GET", BUCKET_NAME, unique_filename, expires=timedelta(days=7))
