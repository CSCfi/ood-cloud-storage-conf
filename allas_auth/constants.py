import os
import pwd

USER = pwd.getpwuid(os.geteuid()).pw_name

TMPDIR = os.path.join("/tmp", USER)

# OS_* are env variables used by OpenStack (CLI).
BASE_OS_ENV = {
    "OS_AUTH_URL": os.environ.get("OS_AUTH_URL", "https://pouta.csc.fi:5001/v3"),
    "OS_REGION_NAME": os.environ.get("OS_REGION_NAME", "regionOne"),
    "OS_INTERFACE": os.environ.get("OS_INTERFACE", "public"),
    "OS_IDENTITY_API_VERSION": os.environ.get("OS_IDENTITY_API_VERSION", "3"),
    "OS_USERNAME": os.environ.get("OS_USERNAME", USER),
}

OS_STORAGE_URL_BASE = "https://a3s.fi:443/swift/v1/"

RCLONE_CONF = os.environ.get(
    "RCLONE_CONFIG", os.path.join(os.path.expanduser("~"), ".config/rclone/rclone.conf")
)

RCLONE_BASE_S3_CONF = {
    "type": "s3",
    "provider": "Other",
    "env_auth": "false",
    "access_key_id": "",
    "secret_access_key": "",
    "endpoint": "a3s.fi",
    "acl": "private",
}

RCLONE_BASE_SWIFT_CONF = {
    "type": "swift",
    "env_auth": "false",
    "auth_token": "",
    "storage_url": "",
}
