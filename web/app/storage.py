# web/app/storage.py
import os, uuid, datetime, pathlib, json
from minio import Minio
from minio.error import S3Error

ENDPOINT     = os.getenv("S3_ENDPOINT", "minio:9000")
ACCESS_KEY   = os.getenv("S3_ACCESS_KEY", "minioadmin")
SECRET_KEY   = os.getenv("S3_SECRET_KEY", "minioadminsecret")
BUCKET       = os.getenv("S3_BUCKET", "travellito")

# Optional parameters useful for external providers (e.g. Yandex Object Storage)
# Set S3_SECURE="true" and S3_REGION="ru-central1" in your environment if needed.
SECURE_ENV   = os.getenv("S3_SECURE", "false").lower() == "true"
REGION       = os.getenv("S3_REGION")

# Use this for external access (from browser)
PUBLIC_ENDPOINT = os.getenv("PUBLIC_S3_ENDPOINT", "localhost:9000")

# Choose secure flag automatically unless explicitly specified
if not SECURE_ENV:
    # Default to insecure when working with local MinIO, otherwise secure
    SECURE_ENV = not ENDPOINT.startswith("minio") and not ENDPOINT.startswith("localhost")

client_kwargs = {
    "access_key": ACCESS_KEY,
    "secret_key": SECRET_KEY,
    "secure": SECURE_ENV,
}
if REGION:
    client_kwargs["region"] = REGION

client = Minio(ENDPOINT, **client_kwargs)

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

def upload_qr_template(upload_file):
    """Upload QR template image → returns object key with fixed name"""
    ext = pathlib.Path(upload_file.filename).suffix
    # Use a fixed name for the QR template so we can replace it easily
    object_name = f"qr_template{ext}"
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
    # For browser access, use the public endpoint
    if PUBLIC_ENDPOINT != ENDPOINT:
        return f"http://{PUBLIC_ENDPOINT}/{BUCKET}/{object_name}"
    else:
        return client.presigned_get_object(
            BUCKET, object_name,
            expires=datetime.timedelta(seconds=seconds)
        )
