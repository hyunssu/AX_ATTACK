from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from typing import Optional
import requests
from minio import Minio
import uuid
import io
import os
from datetime import timedelta

app = FastAPI()

DIFY_API_URL = os.getenv("DIFY_URL")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_EXT_ENDPOINT = os.getenv("MINIO_EXT_ENDPOINT")
MINIO_USER = os.getenv("MINIO_USER")
MINIO_PASSWORD = os.getenv("MINIO_PASSWORD")
BUCKET_NAME = "chat-attachments"

minio_ext_client = Minio(
    MINIO_EXT_ENDPOINT,
    access_key=MINIO_USER,
    secret_key=MINIO_PASSWORD,
    secure=False
)

class ChatRequest(BaseModel):
    input_message: str
    file_url: Optional[str] = None
    file_type: Optional[str] = "document" 

@app.post("/api/chat")
def chat_with_dify(req: ChatRequest):
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": {
            "input_message": req.input_message
        },
        "response_mode": "blocking",
        "user": "local-test-user"
    }

    if req.file_url:
        payload["inputs"]["input_file"] = {
            "transfer_method": "remote_url",
            "url": req.file_url,
            "type": req.file_type
        }

    try:
        response = requests.post(DIFY_API_URL, headers=headers, json=payload)
        
        # 🚨 여기서 Dify가 왜 거절했는지 진짜 이유를 화면에 띄워줄 거야!
        if response.status_code != 200:
            return {"output_message": f"🚨 Dify 거절 사유: {response.text}"}
            
        data = response.json()
        output_msg = data.get("data", {}).get("outputs", {}).get("output_message", "결과를 파싱하지 못했어.")
        return {"output_message": output_msg}
    except Exception as e:
        return {"output_message": f"Dify 통신 에러: {str(e)}"}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_data = await file.read()
        
        minio_ext_client.put_object(
            BUCKET_NAME,
            unique_filename,
            io.BytesIO(file_data),
            len(file_data),
            content_type=file.content_type
        )
        
        public_url = minio_ext_client.get_presigned_url(
            "GET", BUCKET_NAME, unique_filename, expires=timedelta(days=1)
        )

        #내부망 IP를 사용할 경우, 강제 변환
        public_url = public_url.replace("storage:9000", "43.201.6.244:62408")
        
        return {"status": "success", "file_name": file.filename, "file_url": public_url}
    except Exception as e:
        return {"status": "error", "message": str(e)}
