import configparser
import copy
import os
import shutil
import time

from .constants import (
    LUMIO_ENDPOINTS,
    LUMIO_RCLONE_CONF,
    OS_STORAGE_URL_BASE,
    RCLONE_BASE_S3_CONF,
    RCLONE_BASE_SWIFT_CONF,
    RCLONE_CONF,
)
from .utils import create_private_dir


class RcloneError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def full_message(self):
        return f"{self.message}: {str(self.__context__)}"


def remote_name(project_name, s3):
    if s3:
        return f"s3allas-{project_name}"
    else:
        return f"allas-{project_name}"


def contains_comments(config_file):
    try:
        with open(config_file, "r") as f:
            lines = f.readlines()
            return any(map(lambda l: l.lstrip().startswith(("#", ";")), lines))
    except FileNotFoundError:
        return False


# Reads current Rclone config, or return empty if no config exists.
def current_rclone_conf():
    config = configparser.ConfigParser(strict=False)
    # Missing config file is handled ok (nothing added to config).
    try:
        config.read(RCLONE_CONF)
    except configparser.Error as err:
        raise RcloneError("Could not read Rclone config") from err
    return config


def current_lumio_conf():
    config = configparser.ConfigParser(strict=False)
    # Missing config file is handled ok (nothing added to config).
    try:
        config.read(LUMIO_RCLONE_CONF)
    except configparser.Error as err:
        raise RcloneError("Could not read Rclone config") from err
    return config


# Writes Rclone config to disk.
def write_rclone_conf(conf):
    try:
        create_private_dir(os.path.dirname(RCLONE_CONF))
        backup_file = None
        if contains_comments(RCLONE_CONF):
            backup_file = os.path.join(
                os.path.dirname(RCLONE_CONF), f"rclone.conf.{int(time.time())}"
            )
            shutil.copyfile(RCLONE_CONF, backup_file, follow_symlinks=False)
            os.chmod(backup_file, 0o600)

        with open(RCLONE_CONF, "w+") as config_file:
            os.chmod(config_file.name, 0o600)
            conf.write(config_file)

        return backup_file
    except OSError as err:
        raise RcloneError("Could not save updated Rclone config") from err


# Extends existing Rclone rclone with S3 key for project, overwriting existing.
def add_rclone_s3_conf(project_name, access_key, secret):
    conf = current_rclone_conf()
    name = remote_name(project_name, True)
    remote_conf = copy.deepcopy(RCLONE_BASE_S3_CONF)
    remote_conf["access_key_id"] = access_key
    remote_conf["secret_access_key"] = secret
    conf[name] = remote_conf
    return name, write_rclone_conf(conf)


# Copies a list of remotes from the lumio rclone conf to the normal rclone conf.
def copy_lumio_remotes(remotes):
    lumio_conf = current_lumio_conf()
    conf = current_rclone_conf()
    added = []
    for remote in remotes:
        if lumio_conf.has_section(remote):
            conf[remote] = lumio_conf[remote]
            added.append(remote)
    return added, write_rclone_conf(conf)


# Copy over all lumio remotes to the normal rclone conf.
def copy_all_lumio_remotes():
    lumio_conf = current_lumio_conf()
    conf = current_rclone_conf()
    added = []
    for remote in lumio_conf.sections():
        conf[remote] = lumio_conf[remote]
        added.append(remote)
    return added, write_rclone_conf(conf)


# Deletes a remote for a project from the existing Rclone config.
def delete_rclone_remote(remote_names):
    create_private_dir(os.path.dirname(RCLONE_CONF))
    remotes = [remote_names] if isinstance(remote_names, str) else remote_names
    conf = current_rclone_conf()
    for remote in remotes:
        conf.remove_section(remote)
    return write_rclone_conf(conf)


# Get a config value for the remote
def get_remote_option(remote_name, key):
    conf = current_rclone_conf()
    return conf.get(remote_name, key, fallback=None)


def add_rclone_swift_conf(
    project_name, storage_account, auth_token, conf=None, write=True
):
    if conf == None:
        conf = current_rclone_conf()
    name = remote_name(project_name, False)
    remote_conf = copy.deepcopy(RCLONE_BASE_SWIFT_CONF)
    remote_conf["auth_token"] = auth_token
    remote_conf["storage_url"] = f"{OS_STORAGE_URL_BASE}{storage_account}"
    conf[name] = remote_conf
    # Allow updating a conf without saving it to disk, i.e. when generating multiple.
    if write:
        return name, write_rclone_conf(conf)
    else:
        return name, conf


def lumio_remotes():
    conf = current_lumio_conf()
    return conf.sections()


def list_remotes():
    conf = current_rclone_conf()
    # List remotes with name and type.
    return list(
        map(
            lambda remote: {
                "name": remote,
                "type": conf.get(remote, "type", fallback=""),
                "endpoint": "lumio"
                if (
                    any(
                        [
                            endpoint in conf.get(remote, "endpoint", fallback="")
                            for endpoint in LUMIO_ENDPOINTS
                        ]
                    )
                )
                else "other",
            },
            conf.sections(),
        )
    )
