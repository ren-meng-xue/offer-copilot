import logging
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.s3_client = None
        if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                    endpoint_url=settings.S3_ENDPOINT_URL,
                    # 强制使用虚拟托管域名风格，这是腾讯云等云厂商的要求
                    config=Config(s3={"addressing_style": "virtual"}),
                )
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")

    async def upload_file(self, file_obj: BinaryIO, file_name: str) -> str:
        """
        上传文件到存储桶并返回公开访问 URL。
        """
        if not self.s3_client:
            raise RuntimeError("Storage service is not configured (missing credentials)")

        try:
            # 执行上传
            self.s3_client.upload_fileobj(
                file_obj,
                settings.S3_BUCKET_NAME,
                file_name,
                ExtraArgs={"ACL": "public-read"}  # 允许公开读取，方便 Celery 下载
            )
            
            # 构造返回 URL
            # 腾讯云格式通常是: https://<bucket>.cos.<region>.myqcloud.com/<file_name>
            # 或者直接从 endpoint 推导
            base_url = settings.S3_ENDPOINT_URL.replace("://", f"://{settings.S3_BUCKET_NAME}.")
            return f"{base_url}/{file_name}"
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise RuntimeError(f"文件上传失败: {e}")


storage_service = StorageService()
