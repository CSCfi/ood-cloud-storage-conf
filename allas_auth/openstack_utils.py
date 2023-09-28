import json
import os
import subprocess
from functools import wraps
from subprocess import CalledProcessError

import requests

from .constants import BASE_OS_ENV


class OpenStackError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def cause(self):
        if isinstance(self.__context__, CalledProcessError):
            return f"openstack exited with status {self.__context__.returncode}: {self.__context__.stderr}"
        elif not self.__context__ is None:
            return str(self.__context__)
        else:
            return None

    def full_message(self):
        cause = self.cause()
        if cause is None:
            return self.message
        else:
            return f"{self.message}: {cause}"


def wrap_error(err_msg):
    def _outer(os_func):
        @wraps(os_func)
        def _inner(*args, **kwargs):
            try:
                return os_func(*args, **kwargs)
            except CalledProcessError as err:
                raise OpenStackError(err_msg) from err

        return _inner

    return _outer


# Run a process with env variables configured for openstack authentication.
# Uses either token auth (os_token) or password auth (os_password).
# Set os_project_id for commands that require a scope.
def run_with_os_env(
    *args, os_password=None, os_token=None, os_project_id=None, **kwargs
):
    default_kwargs = {"capture_output": True, "text": True}
    env = {**os.environ.copy(), **BASE_OS_ENV, **kwargs.get("env", {})}
    # Configure OpenStack (CLI) using env vars (OS_*).
    if not os_project_id is None:
        env["OS_PROJECT_ID"] = os_project_id
    if not os_password is None:
        env["OS_AUTH_TYPE"] = "v3password"
        env["OS_PASSWORD"] = os_password
    elif not os_token is None:
        env["OS_AUTH_TYPE"] = "v3token"
        env["OS_TOKEN"] = os_token
    kwargs = {**default_kwargs, **kwargs, "env": env}
    result = subprocess.run(*args, **kwargs)
    result.check_returncode()
    return result


# Issue a new unscoped openstack token (valid for all projects)
@wrap_error("Could not issue new openstack token")
def get_unscoped_token(os_password):
    res = run_with_os_env(
        ["openstack", "token", "issue", "--format=json"], os_password=os_password
    )
    return json.loads(res.stdout)


# Issue a new scoped openstack token (valid only for one project)
@wrap_error("Could not issue new openstack token for project")
def create_scoped_token(unscoped_token, project_id):
    res = run_with_os_env(
        ["openstack", "token", "issue", "--format=json"],
        os_project_id=project_id,
        os_token=unscoped_token["id"],
    )
    return json.loads(res.stdout)


# Issue a new scoped openstack token (valid only for one project)
@wrap_error("Could not get object store account")
def get_storage_account(scoped_token, project_id):
    res = run_with_os_env(
        ["openstack", "object", "store", "account", "show", "--format=json"],
        os_project_id=project_id,
        os_token=scoped_token["id"],
    )
    info = json.loads(res.stdout)
    return info.get("Account")


# Get info for an openstack token (scoped or unscoped).
def get_token_info(os_token):
    url = f"{BASE_OS_ENV['OS_AUTH_URL']}/auth/tokens"
    headers = {"X-Auth-Token": os_token, "X-Subject-Token": os_token}
    response = requests.get(url, headers=headers)
    return response.json()


# Revoke an openstack token.
def revoke_token(os_token):
    # For some reason openstack token revoke does not work with only the token, send request manually.
    url = f"{BASE_OS_ENV['OS_AUTH_URL']}/auth/tokens"
    headers = {"X-Auth-Token": os_token, "X-Subject-Token": os_token}
    response = requests.delete(url, headers=headers)
    # Check if revokation successful or already invalid.
    if not (response.status_code == 204 or response.status_code == 401):
        response.raise_for_status()


# List all the user's projects.
@wrap_error("Could not get openstack projects")
def get_projects(unscoped_token):
    res = run_with_os_env(
        [
            "openstack",
            "project",
            "list",
            "--my-projects",
            "--format=json",
        ],
        os_token=unscoped_token["id"],
    )
    return json.loads(res.stdout)


# List all S3 tokens for a project.
@wrap_error("Could not get S3 tokens for project")
def get_s3_tokens(unscoped_token, project_id):
    res = run_with_os_env(
        [
            "openstack",
            "ec2",
            "credentials",
            "list",
            "--format=json",
        ],
        os_project_id=project_id,
        os_token=unscoped_token["id"],
    )
    tokens = list(
        filter(lambda tok: tok["Project ID"] == project_id, json.loads(res.stdout))
    )
    return tokens


# Get an existing S3 token if it exists, otherwise new
def get_or_create_s3_token(unscoped_token, project_id):
    s3_tokens = get_s3_tokens(unscoped_token, project_id)
    if len(s3_tokens) == 0:
        token = create_s3_token(unscoped_token, project_id)
        s3_tokens = [
            {
                "Access": token["access"],
                "Project ID": token["project_id"],
                "Secret": token["secret"],
                "User ID": token["user_id"],
            }
        ]
    token = s3_tokens[0]
    return token


# Create an S3 token for a project.
@wrap_error("Could not create a new S3 token for project")
def create_s3_token(unscoped_token, project_id):
    res = run_with_os_env(
        [
            "openstack",
            "ec2",
            "credentials",
            "create",
            "--format=json",
        ],
        os_project_id=project_id,
        os_token=unscoped_token["id"],
    )
    return json.loads(res.stdout)


# Delete an S3 token for a project.
@wrap_error("Could not delete S3 token for project")
def delete_s3_token(unscoped_token, project_id, token_id):
    return run_with_os_env(
        ["openstack", "ec2", "credentials", "delete", token_id],
        os_project_id=project_id,
        os_token=unscoped_token["id"],
    )
