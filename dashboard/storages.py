from django.conf import settings

USE_S3 = settings.USE_S3

if USE_S3:
    from storages.backends.s3boto3 import S3Boto3Storage

    class StaticRootS3Boto3Storage(S3Boto3Storage):
        location = "static"
        default_acl = None
        file_overwrite = True
        querystring_auth = False

    class MediaRootS3Boto3Storage(S3Boto3Storage):
        location = "media"
        default_acl = "private"
        file_overwrite = False
        querystring_auth = True

    class PrivateMediaStorage(MediaRootS3Boto3Storage):
        pass

else:
    # Local fallback for dev
    from django.core.files.storage import FileSystemStorage
    from pathlib import Path

    class StaticRootS3Boto3Storage(FileSystemStorage):
        def __init__(self, *args, **kwargs):
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
        def __init__(self, *args, **kwargs):
            local_root = getattr(settings, "PRIVATE_MEDIA_ROOT", Path("media"))
            super().__init__(location=str(local_root), base_url=None, *args, **kwargs)
