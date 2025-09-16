import os
import json
import sys
from pathlib import Path

import boto3
from botocore.config import Config

BUCKET = os.getenv("S3_BUCKET", os.getenv("AWS_S3_BUCKET", "finelo-quiz-assets"))
ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")

s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=ENDPOINT,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    config=Config(s3={"addressing_style": "path"}),
)


def ensure_bucket():
    existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if BUCKET not in existing:
        s3.create_bucket(Bucket=BUCKET)
        print(f"✅ Created bucket {BUCKET}")
    else:
        print(f"ℹ️ Bucket {BUCKET} already exists")


def put_cors():
    cors = {
        "CORSRules": [
            {
                "AllowedOrigins": ["*"],
                "AllowedMethods": ["GET", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag", "Content-Length", "Content-Type"],
                "MaxAgeSeconds": 300,
            }
        ]
    }
    s3.put_bucket_cors(Bucket=BUCKET, CORSConfiguration=cors)
    print("✅ Applied CORS to bucket")


def upload_assets():
    src = Path(__file__).resolve().parents[1] / "app" / "assets" / "matching_images"
    if not src.exists():
        print(f"⚠️ Assets directory not found: {src}")
        return
    for p in src.glob("*.png"):
        key = f"matching_images/{p.name}"
        s3.upload_file(str(p), BUCKET, key)
        print(f"⬆️  Uploaded {p.name} to s3://{BUCKET}/{key}")


if __name__ == "__main__":
    try:
        ensure_bucket()
        put_cors()
        upload_assets()
    except Exception as e:
        print(f"❌ S3 bootstrap error: {e}", file=sys.stderr)
        sys.exit(1)
    print("🎉 S3 bootstrap finished") 