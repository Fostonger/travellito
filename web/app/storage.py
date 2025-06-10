# web/app/storage.py
import os, uuid, datetime, pathlib
from minio import Minio
from minio.error import S3Error

ENDPOINT     = os.getenv("S3_ENDPOINT", "minio:9000")
ACCESS_KEY   = os.getenv("S3_ACCESS_KEY", "minioadmin")
SECRET_KEY   = os.getenv("S3_SECRET_KEY", "minioadminsecret")
BUCKET       = os.getenv("S3_BUCKET", "tour-images")

client = Minio(
    ENDPOINT,
    access_key=ACCESS_KEY,
    secret_key=SECRET_KEY,
    secure=False                       # internal network → HTTP
)

if not client.bucket_exists(BUCKET):
    client.make_bucket(BUCKET)

def upload_image(upload_file):
    """Upload FastAPI UploadFile → returns object key"""
    ext = pathlib.Path(upload_file.filename).suffix
    object_name = f"{uuid.uuid4().hex}{ext}"
    upload_file.file.seek(0)
    client.put_object(
        bucket_name=BUCKET,
        object_name=object_name,
        data=upload_file.file,
        length=-1,                      # multipart
        part_size=10*1024*1024,
        content_type=upload_file.content_type
    )
    return object_name

def presigned(object_name, seconds=3600):
    return client.presigned_get_object(
        BUCKET, object_name,
        expires=datetime.timedelta(seconds=seconds)
    )