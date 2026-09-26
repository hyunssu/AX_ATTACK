import io
import uuid
from datetime import timedelta

from minio import Minio

from config import BUCKET_NAME, MINIO_EXT_ENDPOINT, MINIO_PASSWORD, MINIO_USER

minio_client = Minio(
    MINIO_EXT_ENDPOINT,
    access_key=MINIO_USER,
    secret_key=MINIO_PASSWORD,
    secure=False
)


def upload_file(file_bytes: bytes, filename: str, content_type: str) -> tuple[str, str]:
    """Returns (presigned_url, object_name). object_name은 만료 없이 재다운로드에 사용."""
    unique_filename = f"{uuid.uuid4()}_{filename}"
    minio_client.put_object(
        BUCKET_NAME, unique_filename, io.BytesIO(file_bytes), len(file_bytes), content_type=content_type
    )
    url = minio_client.get_presigned_url("GET", BUCKET_NAME, unique_filename, expires=timedelta(days=7))
    return url, unique_filename


def download_file(object_name: str) -> bytes:
    """MinIO에서 파일을 다운로드해 bytes로 반환한다."""
    response = minio_client.get_object(BUCKET_NAME, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
