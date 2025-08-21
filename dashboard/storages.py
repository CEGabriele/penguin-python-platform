
import os
from django.conf import settings

USE_S3 = os.getenv("USE_S3", "false").lower() == "true"

if USE_S3:
    from storages.backends.s3boto3 import S3Boto3Storage

    class StaticRootS3Boto3Storage(S3Boto3Storage):
        location = "static"
        default_acl = "public-read"
        file_overwrite = True

    class MediaRootS3Boto3Storage(S3Boto3Storage):
        location = "media"
        default_acl = None
        file_overwrite = False

    class PrivateMediaStorage(MediaRootS3Boto3Storage):
        """Backwards-compat alias used by old migrations."""
        pass
else:
    from django.core.files.storage import FileSystemStorage
    from pathlib import Path
    class StaticRootS3Boto3Storage(FileSystemStorage):
        def __init__(self, *args, **kwargs):
            # Serve static from /static/ in DEBUG; collectstatic can still use STATIC_ROOT
            static_root = getattr(settings, "STATIC_ROOT", Path("staticfiles"))
            kwargs.setdefault("location", str(static_root))
            kwargs.setdefault("base_url", None)
            super().__init__(*args, **kwargs)

    class MediaRootS3Boto3Storage(FileSystemStorage):
        def __init__(self, *args, **kwargs):
            local_root = getattr(settings, "MEDIA_ROOT", Path("media"))
            kwargs.setdefault("location", str(local_root))
            kwargs.setdefault("base_url", None)
            super().__init__(*args, **kwargs)
    
    class PrivateMediaStorage(FileSystemStorage):
        """Local fallback for dev."""
        def __init__(self, *args, **kwargs):
            local_root = getattr(settings, "PRIVATE_MEDIA_ROOT", Path("media"))
            super().__init__(location=str(local_root), base_url=None, *args, **kwargs)