import os

from flask import Flask, jsonify, request

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
)
from allas_auth.token_handler import (
    get_cached_os_token,
    get_cached_os_tokens,
    remove_cached_os_tokens,
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
        add_rclone_s3_conf(project["Name"], token["Access"], token["Secret"])
    except OpenStackError as err:
        return str(err), 500
    except OSError as err:
        return f"Could not save updated Rclone config: {err}", 500
    return "", 200


@app.route("/delete", methods=["POST"])
def delete_project():
    req_remote = request.form.get("remote")
    if req_remote is None:
        return "Missing remote", 400
    try:
        delete_rclone_s3_conf(req_remote)
    except OSError as err:
        return f"Could not save updated Rclone config: {err}", 500
    return "", 200


@app.route("/revoke_remote", methods=["POST"])
def revoke_remote():
    req_remote = request.form.get("remote")
    if req_remote is None:
        return "Missing remote", 400

    # Determine project name from remote name (i.e. allas-project_123 => project_123).
    # Safer (but slower) option would be to find project based on access_key_id only.
    split_remote = req_remote.split("-", 1)
    if len(split_remote) < 2:
        return "Could not get project name from remote", 400
    project_name = split_remote[-1]

    os_token = get_cached_os_token()
    if os_token is None:
        return "Missing token", 401

    try:
        projects = get_projects(os_token)

        project = next(
            (p for p in projects if p["Name"] == project_name),
            None,
        )
        if project is None:
            return "Invalid project name or ID", 400
        s3_token_id = access_key_id(req_remote)
        if s3_token_id is None:
            return "Remote is not an S3 remote or does not have an access key", 400
        delete_s3_token(os_token, project["ID"], s3_token_id)
        delete_rclone_s3_conf(req_remote)
    except OpenStackError as err:
        return str(err), 500
    except OSError as err:
        return f"Could not save updated Rclone config: {err}", 500
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
    return jsonify(list_remotes())


# Returns the expiry time of the current openstack token.
@app.get("/status")
def status():
    os_token = get_cached_os_token()
    # TODO: Actually validate that token works (has not been revoked).
    if os_token is None:
        return "Missing token", 401
    else:
        return os_token["expires"].strftime("%d-%m-%Y %H:%M:%S %Z"), 200


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
