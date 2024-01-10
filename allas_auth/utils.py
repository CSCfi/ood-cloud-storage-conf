import os
import pathlib
import pwd
import subprocess

from .constants import LUMIO_CONF_TOOL, S3CMD_CONF
from .openstack_utils import wrap_error


# Create directory with perms 0o700, or chmod existing dir to 0o700.
def create_private_dir(dir):
    pathlib.Path(dir).mkdir(parents=True, exist_ok=True, mode=0o700)
    pwuid = pwd.getpwuid(os.geteuid())
    os.chown(dir, pwuid.pw_uid, pwuid.pw_gid)
    os.chmod(dir, 0o700)


# Uses LUMI-o-tools lumio-conf to add the s3cmd configuration to $HOME/s3cmd
@wrap_error("Could not create s3cmd configuration")
def configure_s3cmd(project_id, access_key, secret):
    env = {
        **os.environ.copy(),
        "LUMIO_PROJECTID": project_id,
        "LUMIO_S3_ACCESS": access_key,
        "LUMIO_S3_SECRET": secret,
    }
    result = subprocess.run(
        [
            LUMIO_CONF_TOOL,
            "--noninteractive",
            "--skip-validation",
            "all",
            "--configure-only",
            "s3cmd",
            "--config-path",
            f"s3cmd:#{S3CMD_CONF}"
        ],
        env=env,
        capture_output=True,
        text=True
    )
    result.check_returncode()
