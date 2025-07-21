# web/app/storage.py
import os, uuid, datetime, pathlib, json
from minio import Minio
from minio.error import S3Error

ENDPOINT     = os.getenv("S3_ENDPOINT", "minio:9000")
ACCESS_KEY   = os.getenv("S3_ACCESS_KEY", "minioadmin")
SECRET_KEY   = os.getenv("S3_SECRET_KEY", "minioadminsecret")
BUCKET       = os.getenv("S3_BUCKET", "tour-images")
# Use this for external access (from browser)
PUBLIC_ENDPOINT = os.getenv("PUBLIC_S3_ENDPOINT", "localhost:9000")

client = Minio(
    ENDPOINT,
    access_key=ACCESS_KEY,
    secret_key=SECRET_KEY,
    secure=False                       # internal network → HTTP
)

if not client.bucket_exists(BUCKET):
    client.make_bucket(BUCKET)

# Set bucket policy to allow public read access
try:
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{BUCKET}/*"]
            }
        ]
    }
    client.set_bucket_policy(BUCKET, json.dumps(policy))
except Exception as e:
    print(f"Error setting bucket policy: {str(e)}")

# Always set the CORS policy (even if bucket already exists)
try:
    cors_config = {
        'CORSRules': [
            {
                'AllowedHeaders': ['*'],
                'AllowedMethods': ['GET', 'PUT', 'POST'],
                'AllowedOrigins': ['*'],
                'ExposeHeaders': ['ETag', 'Content-Length', 'Content-Type'],
                'MaxAgeSeconds': 3600
            }
        ]
    }
    client.set_bucket_cors(BUCKET, cors_config)
except Exception as e:
    print(f"Error setting CORS policy: {str(e)}")

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