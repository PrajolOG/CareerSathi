import os
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

class MinioHandler:
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

    def get_all_images(self, bucket_name: str = None):
        """Fetch all image URLs from the bucket."""
        target_bucket = bucket_name or self.bucket_name
        try:
            # Check if bucket exists    
            if not self.client.bucket_exists(target_bucket):
                print(f"Bucket {target_bucket} does not exist.")
                return []

            # List objects in bucket
            objects = self.client.list_objects(target_bucket, recursive=True)
            image_urls = []
            
            for obj in objects:
                # Basic check for image extensions
                if obj.object_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
                    from datetime import timedelta
                    url = self.client.presigned_get_object(
                        target_bucket, 
                        obj.object_name,
                        expires=timedelta(days=7)
                    )
                    image_urls.append(url)
            
            return image_urls
        except Exception as e:
            print(f"Error fetching images from MinIO: {e}")
            return []

    def list_buckets(self):
        """Fetch all buckets with their object counts."""
        try:
            buckets = self.client.list_buckets()
            results = []
            for b in buckets:
                try:
                    objects = list(self.client.list_objects(b.name, recursive=True))
                    file_count = len(objects)
                except Exception:
                    file_count = 0
                results.append({"name": b.name, "creation_date": b.creation_date, "file_count": file_count})
            return results
        except Exception as e:
            print(f"Error listing buckets: {e}")
            return []

    def get_total_storage_bytes(self):
        """Calculate total storage used across all buckets in bytes."""
        total_bytes = 0
        try:
            buckets = self.client.list_buckets()
            for b in buckets:
                try:
                    objects = self.client.list_objects(b.name, recursive=True)
                    for obj in objects:
                        total_bytes += obj.size
                except Exception:
                    continue
            return total_bytes
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
            print(f"Error creating bucket {bucket_name}: {e}")
            return False, str(e)

    def ensure_bucket(self, bucket_name: str):
        """Ensure bucket exists (create if missing)."""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
            return True, "Bucket ready"
        except Exception as e:
            print(f"Error ensuring bucket {bucket_name}: {e}")
            return False, str(e)

    def delete_bucket(self, bucket_name: str):
        """Delete a bucket (must be empty)."""
        try:
            if self.client.bucket_exists(bucket_name):
                # Optionally, empty the bucket first before deleting to ensure it succeeds.
                objects = self.client.list_objects(bucket_name, recursive=True)
                for obj in objects:
                    self.client.remove_object(bucket_name, obj.object_name)
                    
                self.client.remove_bucket(bucket_name)
                return True, "Bucket deleted successfully"
            return False, "Bucket does not exist"
        except Exception as e:
            print(f"Error deleting bucket {bucket_name}: {e}")
            return False, str(e)

    def migrate_bucket(self, source_bucket: str, target_bucket: str, objects_to_migrate: list = None):
        """Migrate (copy) all objects from one bucket to another."""
        try:
            if not self.client.bucket_exists(source_bucket):
                return False, f"Source bucket '{source_bucket}' does not exist"
            if not self.client.bucket_exists(target_bucket):
                return False, f"Target bucket '{target_bucket}' does not exist"

            from minio.commonconfig import CopySource
            
            if objects_to_migrate:
                for obj_name in objects_to_migrate:
                    self.client.copy_object(
                        target_bucket,
                        obj_name,
                        CopySource(source_bucket, obj_name)
                    )
                    self.client.remove_object(source_bucket, obj_name)
            else:
                objects = self.client.list_objects(source_bucket, recursive=True)
                for obj in objects:
                    # Copy object
                    self.client.copy_object(
                        target_bucket,
                        obj.object_name,
                        CopySource(source_bucket, obj.object_name)
                    )
                    # Remove object from source bucket
                    self.client.remove_object(source_bucket, obj.object_name)

            return True, "Data migrated successfully"
        except Exception as e:
            print(f"Error migrating data from {source_bucket} to {target_bucket}: {e}")
            return False, str(e)

    def list_bucket_objects(self, bucket_name: str):
        """Fetch all objects inside a specific bucket."""
        try:
            if not self.client.bucket_exists(bucket_name):
                return []

            objects = self.client.list_objects(bucket_name, recursive=True)
            results = []
            from datetime import timedelta
            for obj in objects:
                size_mb = obj.size / (1024 * 1024) if obj.size else 0
                object_name_lower = (obj.object_name or "").lower()
                is_image = object_name_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))

                try:
                    presigned_url = self.client.presigned_get_object(
                        bucket_name,
                        obj.object_name,
                        expires=timedelta(days=7)
                    )
                except Exception:
                    presigned_url = ""

                results.append({
                    "name": obj.object_name,
                    "size": f"{size_mb:.2f} MB",
                    "last_modified": obj.last_modified,
                    "presigned_url": presigned_url,
                    "is_image": is_image,
                })
            return results
        except Exception as e:
            print(f"Error listing objects in bucket {bucket_name}: {e}")
            return []

    def upload_file(self, bucket_name: str, object_name: str, file_data: bytes, content_type: str = "application/octet-stream"):
        """Upload a generic file/object to a bucket."""
        try:
            from io import BytesIO
            data_stream = BytesIO(file_data)
            self.client.put_object(
                bucket_name,
                object_name,
                data_stream,
                length=len(file_data),
                content_type=content_type
            )
            return True, "File uploaded successfully"
        except Exception as e:
            print(f"Error uploading file to {bucket_name}: {e}")
            return False, str(e)
            
    def delete_objects(self, bucket_name: str, object_names: list):
        """Delete multiple objects from a bucket."""
        try:
            for obj in object_names:
                self.client.remove_object(bucket_name, obj)
            return True, "Objects deleted successfully"
        except Exception as e:
            print(f"Error deleting objects in {bucket_name}: {e}")
            return False, str(e)

# Singleton instance
minio_client = MinioHandler()
