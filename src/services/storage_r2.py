"""
Cloudflare R2 Storage Handler
S3-compatible object storage for images and files
"""
import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import Optional, BinaryIO, List
import mimetypes
from pathlib import Path


class R2Storage:
    """Cloudflare R2 storage handler using boto3 (S3-compatible)"""
    
    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        public_url: Optional[str] = None
    ):
        """
        Initialize R2 storage client
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            public_url: Public URL for bucket (e.g., https://yourbucket.your-domain.com)
        """
        self.account_id = account_id or os.getenv('R2_ACCOUNT_ID')
        self.access_key_id = access_key_id or os.getenv('R2_ACCESS_KEY_ID')
        self.secret_access_key = secret_access_key or os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = bucket_name or os.getenv('R2_BUCKET_NAME')
        self.public_url = public_url or os.getenv('R2_PUBLIC_URL', '')
        
        if not all([self.account_id, self.access_key_id, self.secret_access_key, self.bucket_name]):
            raise ValueError("Missing required R2 configuration. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME")
        
        # R2 endpoint URL format
        endpoint_url = f'https://{self.account_id}.r2.cloudflarestorage.com'
        
        # Initialize S3 client configured for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'  # R2 uses 'auto' region
        )
        
        print(f"✅ R2 storage initialized for bucket: {self.bucket_name}")
    
    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        folder: str = 'uploads',
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload file to R2
        
        Args:
            file_data: File binary data
            filename: Name of the file
            folder: Folder/prefix in bucket (default: 'uploads')
            content_type: MIME type (auto-detected if not provided)
        
        Returns:
            Public URL of the uploaded file
        """
        # Generate unique key
        key = f"{folder}/{filename}"
        
        # Auto-detect content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'
        
        try:
            # Upload to R2
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_data,
                ContentType=content_type,
                # Make object publicly readable
                ACL='public-read'
            )
            
            # Return public URL
            if self.public_url:
                return f"{self.public_url}/{key}"
            else:
                # Fallback to R2 dev URL (not recommended for production)
                return f"https://{self.bucket_name}.r2.dev/{key}"
        
        except ClientError as e:
            print(f"❌ Error uploading to R2: {e}")
            raise
    
    def delete_file(self, file_url: str) -> bool:
        """
        Delete file from R2
        
        Args:
            file_url: Full URL or key of the file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract key from URL
            if file_url.startswith('http'):
                # Parse key from URL
                key = file_url.split(f"{self.bucket_name}/")[-1]
            else:
                key = file_url
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        
        except ClientError as e:
            print(f"❌ Error deleting from R2: {e}")
            return False
    
    def get_file_url(self, key: str) -> str:
        """
        Get public URL for a file
        
        Args:
            key: File key in bucket
        
        Returns:
            Public URL
        """
        if self.public_url:
            return f"{self.public_url}/{key}"
        else:
            return f"https://{self.bucket_name}.r2.dev/{key}"
    
    def list_files(self, prefix: str = '') -> list:
        """
        List files in bucket
        
        Args:
            prefix: Filter by prefix/folder
        
        Returns:
            List of file keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        
        except ClientError as e:
            print(f"❌ Error listing R2 files: {e}")
            return []


def upload_company_file(company_id: int, file_data: BinaryIO, filename: str, 
                       file_type: str = 'uploads', content_type: Optional[str] = None) -> Optional[str]:
    """
    Upload a file for a specific company with proper folder separation
    
    Args:
        company_id: Company ID for folder separation
        file_data: File binary data
        filename: Name of the file
        file_type: Type of file (logos, documents, images, etc.)
        content_type: MIME type (auto-detected if not provided)
    
    Returns:
        Public URL of the uploaded file or None if R2 not configured
    """
    r2 = get_r2_storage()
    if not r2:
        return None
    
    try:
        return r2.upload_file(
            file_data=file_data,
            filename=filename,
            folder=f'company_{company_id}/{file_type}',
            content_type=content_type
        )
    except Exception as e:
        print(f"❌ Failed to upload file for company {company_id}: {e}")
        return None


def delete_company_file(company_id: int, file_url: str) -> bool:
    """
    Delete a file for a specific company with security check
    
    Args:
        company_id: Company ID for security verification
        file_url: Full URL of the file to delete
    
    Returns:
        True if successful, False otherwise
    """
    r2 = get_r2_storage()
    if not r2:
        return False
    
    # Security check - ensure file belongs to this company
    expected_prefix = f'company_{company_id}/'
    if expected_prefix not in file_url:
        print(f"🚨 Security: Company {company_id} attempted to delete file not in their folder: {file_url}")
        return False
    
    return r2.delete_file(file_url)


def list_company_files(company_id: int, file_type: str = '') -> List[str]:
    """
    List files for a specific company
    
    Args:
        company_id: Company ID
        file_type: Optional file type filter (logos, documents, etc.)
    
    Returns:
        List of file keys for this company
    """
    r2 = get_r2_storage()
    if not r2:
        return []
    
    prefix = f'company_{company_id}/'
    if file_type:
        prefix += f'{file_type}/'
    
    return r2.list_files(prefix=prefix)


# Global instance (lazy initialization)
_r2_storage: Optional[R2Storage] = None


def get_r2_storage() -> Optional[R2Storage]:
    """Get or create R2 storage instance"""
    global _r2_storage
    
    if _r2_storage is None:
        try:
            _r2_storage = R2Storage()
        except ValueError as e:
            print(f"⚠️ R2 storage not configured: {e}")
            return None
    
    return _r2_storage


def is_r2_enabled() -> bool:
    """Check if R2 storage is configured"""
    return all([
        os.getenv('R2_ACCOUNT_ID'),
        os.getenv('R2_ACCESS_KEY_ID'),
        os.getenv('R2_SECRET_ACCESS_KEY'),
        os.getenv('R2_BUCKET_NAME')
    ])
