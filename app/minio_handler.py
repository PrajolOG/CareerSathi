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

    def get_all_images(self):
        """Fetch all image URLs from the bucket."""
        try:
            # Check if bucket exists
            if not self.client.bucket_exists(self.bucket_name):
                print(f"Bucket {self.bucket_name} does not exist.")
                return []

            # List objects in bucket
            objects = self.client.list_objects(self.bucket_name, recursive=True)
            image_urls = []
            
            for obj in objects:
                # Basic check for image extensions
                if obj.object_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
                    # Generate a presigned URL that lasts for 7 days (maximum)
                    # For local development, this works best.
                    url = self.client.presigned_get_object(
                        self.bucket_name, 
                        obj.object_name,
                        expires=604800 # 7 days
                    )
                    image_urls.append(url)
            
            return image_urls
        except Exception as e:
            print(f"Error fetching images from MinIO: {e}")
            return []

# Singleton instance
minio_client = MinioHandler()
