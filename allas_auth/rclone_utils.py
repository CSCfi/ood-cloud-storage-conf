import configparser
import copy
import os

from .constants import RCLONE_BASE_REMOTE_CONF, RCLONE_CONF
from .utils import create_private_dir


def remote_name(project_name):
    return f"allas-{project_name}"


# Reads current Rclone config, or return empty if no config exists.
def current_rclone_conf():
    config = configparser.ConfigParser()
    # Missing config file is handled ok (nothing added to config).
    config.read(RCLONE_CONF)
    return config


# Writes Rclone config to disk.
def write_rclone_conf(conf):
    create_private_dir(os.path.dirname(RCLONE_CONF))
    with open(RCLONE_CONF, "w+") as config_file:
        os.chmod(config_file.name, 0o600)
        conf.write(config_file)


# Extends existing Rclone rclone with S3 key for project, overwriting existing.
def add_rclone_s3_conf(project_name, access_key, secret):
    conf = current_rclone_conf()
    remote_conf = copy.deepcopy(RCLONE_BASE_REMOTE_CONF)
    remote_conf["access_key_id"] = access_key
    remote_conf["secret_access_key"] = secret
    conf[remote_name(project_name)] = remote_conf
    write_rclone_conf(conf)


# Deletes a remote for a project from the existing Rclone config.
def delete_rclone_s3_conf(remote_name):
    create_private_dir(os.path.dirname(RCLONE_CONF))
    conf = current_rclone_conf()
    conf.remove_section(remote_name)
    write_rclone_conf(conf)


# S3 access key ID for remote.
def access_key_id(remote_name):
    conf = current_rclone_conf()
    return conf.get(remote_name, "access_key_id", fallback=None)


def list_remotes():
    conf = current_rclone_conf()
    return conf.sections()
