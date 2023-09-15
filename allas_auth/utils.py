import os
import pathlib
import pwd


# Create directory with perms 0o700, or chmod existing dir to 0o700.
def create_private_dir(dir):
    pathlib.Path(dir).mkdir(parents=True, exist_ok=True, mode=0o700)
    pwuid = pwd.getpwuid(os.geteuid())
    os.chown(dir, pwuid.pw_uid, pwuid.pw_gid)
    os.chmod(dir, 0o700)
