import os
from io import BytesIO
from datetime import timedelta

from minio import Minio
from minio.commonconfig import CopySource
from minio.deleteobjects import DeleteObject
from dotenv import load_dotenv

load_dotenv()

class MinioHandler:
    _IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')

    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "False").lower() == "true"
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "carrersathi")
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

    def _get_bucket_object_details(self, bucket_name: str = None, images_only: bool = False):
        """Return normalized metadata for objects in a bucket."""
        target_bucket = bucket_name or self.bucket_name

        if not self.client.bucket_exists(target_bucket):
            return []

        results = []
        for obj in self.client.list_objects(target_bucket, recursive=True):
            object_name = obj.object_name or ""
            is_image = object_name.lower().endswith(self._IMAGE_EXTENSIONS)

            if images_only and not is_image:
                continue

            try:
                presigned_url = self.client.presigned_get_object(
                    target_bucket, object_name, expires=timedelta(days=7)
                )
            except Exception:
                presigned_url = ""

            size_mb = (obj.size or 0) / (1024 * 1024)
            results.append({
                "name": object_name,
                "size": f"{size_mb:.2f} MB",
                "last_modified": obj.last_modified,
                "presigned_url": presigned_url,
                "is_image": is_image,
            })

        return results

    def get_all_images(self, bucket_name: str = None):
        """Fetch all image URLs from the bucket."""
        try:
            images = self._get_bucket_object_details(bucket_name, images_only=True)
            return [obj["presigned_url"] for obj in images if obj["presigned_url"]]
        except Exception as e:
            print(f"Error fetching images: {e}")
            return []

    def list_buckets(self):
        """Fetch all buckets with their object counts (Memory Efficient)."""
        try:
            results = []
            for b in self.client.list_buckets():
                # sum(1 for ...) counts items without loading them all into memory
                file_count = sum(1 for _ in self.client.list_objects(b.name, recursive=True))
                results.append({"name": b.name, "creation_date": b.creation_date, "file_count": file_count})
            return results
        except Exception as e:
            print(f"Error listing buckets: {e}")
            return []

    def get_total_storage_bytes(self):
        """Calculate total storage used across all buckets in bytes."""
        try:
            return sum(
                obj.size for b in self.client.list_buckets()
                for obj in self.client.list_objects(b.name, recursive=True) if obj.size
            )
        except Exception as e:
            print(f"Error calculating total storage: {e}")
            return 0

    def create_bucket(self, bucket_name: str):
        """Create a new bucket."""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                return True, "Bucket created successfully"
            return False, "Bucket already exists"
        except Exception as e:
            return False, str(e)

    def ensure_bucket(self, bucket_name: str):
        """Ensure bucket exists (create if missing)."""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
            return True, "Bucket ready"
        except Exception as e:
            return False, str(e)

    def delete_bucket(self, bucket_name: str):
        """Delete a bucket and all its contents (using fast batch deletion)."""
        try:
            if not self.client.bucket_exists(bucket_name):
                return False, "Bucket does not exist"

            # Batch delete is much faster than deleting 1 by 1
            delete_object_list = [
                DeleteObject(obj.object_name) 
                for obj in self.client.list_objects(bucket_name, recursive=True)
            ]
            
            if delete_object_list:
                errors = self.client.remove_objects(bucket_name, delete_object_list)
                for err in errors:
                    print(f"Error deleting {err.name}: {err.message}")
                
            self.client.remove_bucket(bucket_name)
            return True, "Bucket deleted successfully"
        except Exception as e:
            return False, str(e)

    def migrate_bucket(self, source_bucket: str, target_bucket: str, objects_to_migrate: list = None):
        """Migrate (move) objects from one bucket to another."""
        try:
            if not self.client.bucket_exists(source_bucket): return False, "Source bucket missing"
            if not self.client.bucket_exists(target_bucket): return False, "Target bucket missing"

            # If no specific list is provided, migrate everything
            if not objects_to_migrate:
                objects_to_migrate = [obj.object_name for obj in self.client.list_objects(source_bucket, recursive=True)]

            for obj_name in objects_to_migrate:
                self.client.copy_object(target_bucket, obj_name, CopySource(source_bucket, obj_name))
                self.client.remove_object(source_bucket, obj_name)

            return True, "Data migrated successfully"
        except Exception as e:
            return False, str(e)

    def list_bucket_objects(self, bucket_name: str):
        """Fetch all objects inside a specific bucket."""
        try:
            return self._get_bucket_object_details(bucket_name)
        except Exception as e:
            print(f"Error listing objects: {e}")
            return []

    def upload_file(self, bucket_name: str, object_name: str, file_data: bytes, content_type: str = "application/octet-stream"):
        """Upload a generic file/object to a bucket."""
        try:
            self.client.put_object(
                bucket_name, object_name, BytesIO(file_data),
                length=len(file_data), content_type=content_type
            )
            return True, "File uploaded successfully"
        except Exception as e:
            return False, str(e)
            
    def delete_objects(self, bucket_name: str, object_names: list):
        """Delete multiple objects from a bucket (Using fast batch deletion)."""
        try:
            delete_object_list = [DeleteObject(name) for name in object_names]
            errors = self.client.remove_objects(bucket_name, delete_object_list)
            
            for err in errors:
                print(f"Error deleting {err.name}: {err.message}")
                
            return True, "Objects deleted successfully"
        except Exception as e:
            return False, str(e)

# Singleton instance
minio_client = MinioHandler()