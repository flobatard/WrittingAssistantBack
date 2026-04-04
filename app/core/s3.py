import logging
from functools import lru_cache

import boto3

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_s3_client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.S3_ENDPOINT_URL,
        aws_access_key_id=s.S3_ACCESS_KEY,
        aws_secret_access_key=s.S3_SECRET_KEY,
        region_name="us-east-1",
    )


def _public_url(presigned_url: str) -> str:
    """Replace the internal S3 endpoint with the public-facing URL."""
    s = get_settings()
    if s.S3_ENDPOINT_URL != s.S3_PUBLIC_URL:
        return presigned_url.replace(s.S3_ENDPOINT_URL, s.S3_PUBLIC_URL, 1)
    return presigned_url


def generate_presigned_upload_url(object_key: str, content_type: str) -> str:
    s = get_settings()
    url = get_s3_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": s.S3_BUCKET_NAME,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=s.S3_PRESIGNED_EXPIRY,
    )
    return _public_url(url)


def generate_presigned_download_url(object_key: str) -> str:
    s = get_settings()
    url = get_s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s.S3_BUCKET_NAME,
            "Key": object_key,
        },
        ExpiresIn=s.S3_PRESIGNED_EXPIRY,
    )
    return _public_url(url)


def delete_object(object_key: str) -> None:
    s = get_settings()
    get_s3_client().delete_object(Bucket=s.S3_BUCKET_NAME, Key=object_key)


def delete_objects_by_prefix(prefix: str) -> None:
    """Delete all objects under a given S3 prefix (folder)."""
    s = get_settings()
    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=s.S3_BUCKET_NAME, Prefix=prefix):
        objects = page.get("Contents", [])
        if not objects:
            continue
        client.delete_objects(
            Bucket=s.S3_BUCKET_NAME,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
        )
