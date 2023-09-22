import configparser
import os

from flask import Flask, jsonify, request

from allas_auth.constants import RCLONE_BASE_REMOTE_CONF
from allas_auth.openstack_utils import (
    OpenStackError,
    create_s3_token,
    delete_s3_token,
    get_projects,
    get_s3_tokens,
    get_unscoped_token,
    revoke_token,
)
from allas_auth.rclone_utils import (
    access_key_id,
    add_rclone_s3_conf,
    delete_rclone_s3_conf,
    list_remotes,
    s3_endpoint,
)
from allas_auth.token_handler import (
    get_cached_os_token,
    get_cached_os_tokens,
    save_os_token,
)

app = Flask(__name__)


@app.route("/")
def index():
    return "", 200


@app.route("/add", methods=["POST"])
def add():
    # req_project can be either project ID or name
    req_project = request.form.get("project")
    if req_project is None:
        return "Missing project in request", 400

    os_token = get_cached_os_token()
    if os_token is None:
        return "Missing token", 401
    try:
        projects = get_projects(os_token)

        project = next(
            (p for p in projects if p["Name"] == req_project or p["ID"] == req_project),
            None,
        )
        if project is None:
            return "Invalid project name or ID", 400
        s3_tokens = get_s3_tokens(os_token, project["ID"])
        if len(s3_tokens) == 0:
            token = create_s3_token(os_token, project["ID"])
            s3_tokens = [
                {
                    "Access": token["access"],
                    "Project ID": token["project_id"],
                    "Secret": token["secret"],
                    "User ID": token["user_id"],
                }
            ]
        token = s3_tokens[0]
        backup_file = add_rclone_s3_conf(project["Name"], token["Access"], token["Secret"])
        if not backup_file is None:
            return backup_file, 200
    except OpenStackError as err:
        return str(err), 500
    except OSError as err:
        return f"Could not save updated Rclone config: {err}", 500
    except configparser.Error as err:
        return f"Could not read Rclone config: {err}", 500
    return "", 200


@app.route("/delete", methods=["POST"])
def delete_project():
    req_remote = request.form.get("remote")
    if req_remote is None:
        return "Missing remote", 400
    try:
        backup_file = delete_rclone_s3_conf(req_remote)
        if not backup_file is None:
            return backup_file, 200
    except OSError as err:
        return f"Could not save updated Rclone config: {err}", 500
    except configparser.Error as err:
        return f"Could not read Rclone config: {err}", 500
    return "", 200


@app.route("/revoke_remote", methods=["POST"])
def revoke_remote():
    req_remote = request.form.get("remote")
    if req_remote is None:
        return "Missing remote.", 400

    os_token = get_cached_os_token()
    if os_token is None:
        return "Missing token.", 401

    try:
        s3_token_id = access_key_id(req_remote)
        if s3_token_id is None:
            return "Remote is not an S3 remote or does not have an access token.", 400

        # Need the ID of any project to list S3 tokens.
        any_project = next(iter(get_projects(os_token)), None)
        if any_project is None:
            return "No valid projects found for user."

        s3_tokens = get_s3_tokens(os_token, any_project["ID"])
        s3_token = next(
            (t for t in s3_tokens if t["Access"] == s3_token_id),
            None,
        )
        # Token is valid and is for Allas. Revoke it.
        if not s3_token is None:
            project_id = s3_token["Project ID"]
            delete_s3_token(os_token, project_id, s3_token_id)
        elif s3_endpoint(req_remote) != RCLONE_BASE_REMOTE_CONF["endpoint"]:
            return (
                "Access token for remote can not be revoked as it is not an Allas access token.",
                400,
            )
        backup_file = delete_rclone_s3_conf(req_remote)
        if not backup_file is None:
            return backup_file, 200
    except OpenStackError as err:
        return str(err), 500
    except OSError as err:
        return f"Could not save updated Rclone config: {err}", 500
    except configparser.Error as err:
        return f"Could not read Rclone config: {err}", 500
    return "", 200


@app.get("/projects")
def projects():
    os_token = get_cached_os_token()
    if os_token is None:
        return "Missing token", 401
    try:
        projects = get_projects(os_token)
    except OpenStackError as err:
        return (
            str(err),
            500,
        )
    return jsonify(projects)


@app.get("/remotes")
def remotes():
    try:
        return jsonify(list_remotes())
    except configparser.Error as err:
        return f"Could not read Rclone config: {err}", 500


# Returns the expiry time of the current openstack token.
@app.get("/status")
def status():
    os_token = get_cached_os_token()
    # TODO: Actually validate that token works (has not been revoked).
    if os_token is None:
        return "Missing token", 401
    else:
        return os_token["expires"].strftime("%Y-%m-%d %H:%M:%S %Z"), 200


# Endpoint for removing openstack token. Mostly for debugging (for now). GET for easy use in browser.
@app.route("/revoke_tokens", methods=["GET", "POST"])
def revoke_tokens():
    tokens = get_cached_os_tokens()

    errors = []
    for file, token in tokens:
        try:
            revoke_token(token["id"])
            os.remove(file)
        except OpenStackError as err:
            errors.append(str(err))
        except OSError as err:
            errors.append(str(err))
    if len(errors):
        error_string = "\n".join(errors)
        return f"One or more tokens could not be revoked: {error_string}", 500
    return "", 200


@app.route("/renew_token", methods=["POST"])
def renew_token():
    try:
        password = request.form.get("password")
        if password is None:
            return "Missing password", 401
        os_token = get_unscoped_token(password)
        save_os_token(os_token)
    except OpenStackError as err:
        return (
            str(err),
            500,
        )
    except OSError as err:
        return f"Could not save generated token: {err}", 500
    return "", 200


if __name__ == "__main__":
    app.run()
