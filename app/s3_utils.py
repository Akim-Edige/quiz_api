import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
from urllib.parse import urljoin
from app.config import settings


class S3Service:
    def __init__(self):
        self.s3_client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize S3 client with credentials"""
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
        else:
            # Use default credential chain (IAM roles, environment, etc.)
            self.s3_client = boto3.client('s3', region_name=settings.aws_region)
    
    def generate_presigned_url(self, s3_bucket: str, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for S3 object"""
        if not self.s3_client:
            return None
        
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': s3_bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return response
        except (ClientError, NoCredentialsError):
            return None
    
    def get_public_url(self, s3_bucket: str, s3_key: str) -> str:
        """Generate public URL for S3 object (for CDN or public buckets)"""
        if settings.cdn_domain:
            return urljoin(settings.cdn_domain, s3_key)
        else:
            return f"https://{s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
    
    def get_asset_url(self, s3_bucket: str, s3_key: str, is_private: bool = True) -> str:
        """Get appropriate URL for asset.
        If a CDN domain is configured, always return the CDN/public URL.
        Otherwise, use presigned URLs for private access when possible and fall back to public URL.
        """
        # Prefer CDN/public URL when configured (useful for LocalStack/local dev)
        if settings.cdn_domain:
            return self.get_public_url(s3_bucket, s3_key)
        
        if is_private:
            presigned_url = self.generate_presigned_url(s3_bucket, s3_key)
            return presigned_url or self.get_public_url(s3_bucket, s3_key)
        else:
            return self.get_public_url(s3_bucket, s3_key)


# Global S3 service instance
s3_service = S3Service() 