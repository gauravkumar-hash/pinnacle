from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from config import supabase
import io
import zipfile
from models.model_enums import FileViewerType

def upload_pdf(bucket: str, key: str, file_bytes: bytes):
    try:
        resp = supabase.storage.from_(bucket).upload(
            path=key,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
def delete_file_from_s3(bucket: str, key: str):
    try:
        resp = supabase.storage.from_(bucket).remove([key])
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
    
class SignedURLResponse(BaseModel):
    url: str
    filetype: FileViewerType

def get_signed_url(bucket: str, key: str, expires_in: int = 3600):
    try:
        resp = supabase.storage.from_(bucket).create_signed_url(key, expires_in)
        return SignedURLResponse(url=resp["signedURL"], filetype=FileViewerType.PDF)
    except Exception:
        return None

def check_is_file_exists_in_s3(key: str, bucket_name: str) -> bool:
    # TODO: Issue due to no .exists() method in supabase storage
    # https://github.com/supabase/storage/issues/266
    return get_signed_url(bucket_name, key) is not None

# Version 1 using s3 client to retrieve blob data 
# def get_blob_data_from_s3(key: str, bucket_name: str):
#     try:
#         # Get object from S3-compatible Supabase storage
#         response = s3_client.get_object(Bucket=bucket_name, Key=key)

#         # Read file content from streaming body
#         content = response["Body"].read()

#         return content
#     except s3_client.exceptions.NoSuchKey:
#         raise HTTPException(status_code=404, detail=f"File not found: {key}")
#     except s3_client.exceptions.NoSuchBucket:
#         raise HTTPException(status_code=404, detail=f"Bucket not found: {bucket_name}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to retrieve file: {str(e)}")

def get_blob_data_from_s3(key: str, bucket_name: str):
    return supabase.storage.from_(bucket_name).download(key)

def download_file_from_s3(key: str, bucket_name: str):
    """
    Download a single file from s3
    
    Key is [relative_path]/[filename].pdf
    """
    response = get_blob_data_from_s3(key, bucket_name)
    streams = io.BytesIO(response)  
    
    return StreamingResponse(streams, media_type="application/pdf", 
        headers={
            "Content-Disposition": f"attachment; filename={key}"
        })

class ZipFileRequest(BaseModel):
    key: str 
    filename: str

def download_files_as_zip(keys: list[ZipFileRequest], bucket_name: str, filename: str = "files.zip"):
    """
    Download multiple files as a zip file

    Take note : keys should be distinct to each other in other to identify as different files
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for key in keys:
            file_data = get_blob_data_from_s3(key.key, bucket_name)
            zip_file.writestr(key.filename, file_data)
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
