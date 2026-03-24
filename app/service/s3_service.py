import boto3
from fastapi import status
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
from app.core.config import settings

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
    endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
)

BUCKET = settings.AWS_S3_BUCKET
PROFILE_PHOTO_PREFIX = "profile-photos/"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _build_key(user_id: int, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"{PROFILE_PHOTO_PREFIX}user_{user_id}.{ext}"


async def upload_profile_photo(user_id: int, file: UploadFile) -> str:
    """Upload image to S3. Returns the S3 object key."""

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only JPEG, PNG, and WebP images are allowed."
        )

    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "File too large. Max size is 5 MB."
        )

    key = _build_key(user_id, file.filename)

    try:
        s3_client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=contents,
            ContentType=file.content_type,
        )
    except ClientError as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"S3 upload failed: {e.response['Error']['Message']}",
        )

    return key


def get_presigned_download_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a temporary pre-signed URL for downloading the photo."""
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Could not generate download URL: {e.response['Error']['Message']}",
        )


def delete_profile_photo(s3_key: str) -> None:
    """Delete old photo when user uploads a new one."""
    s3_client.delete_object(Bucket=BUCKET, Key=s3_key)
