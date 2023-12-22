import base64
import json
import os
import re
from functools import wraps
from urllib.parse import unquote

from flask import Flask, escape, jsonify, make_response, request

from allas_auth.constants import OS_STORAGE_URL_BASE, RCLONE_BASE_S3_CONF
from allas_auth.openstack_utils import (
    OpenStackError,
    create_scoped_token,
    delete_s3_token,
    get_or_create_s3_token,
    get_projects,
    get_s3_tokens,
    get_storage_account,
    get_token_info,
    get_unscoped_token,
    revoke_token,
)
from allas_auth.rclone_utils import (
    RcloneError,
    add_rclone_s3_conf,
    add_rclone_swift_conf,
    copy_all_lumio_remotes,
    copy_lumio_remotes,
    delete_rclone_remote,
    get_remote_option,
    list_remotes,
    lumio_remotes,
    write_rclone_conf,
)
from allas_auth.token_handler import (
    get_cached_os_token,
    get_cached_os_tokens,
    parse_expires,
    save_os_token,
)
from allas_auth.utils import configure_s3cmd

app = Flask(__name__)


# Decorator for requiring a valid os_token, passed as a kwarg to handler.
def requires_auth(f):
    @wraps(f)
    def _inner(*args, **kwargs):
        os_token = get_cached_os_token()
        if os_token is None:
            return error_message(f"Missing token.", 401)
        kwargs["os_token"] = os_token
        return f(*args, **kwargs)

    return _inner


# Extracts a parameter from request, returns and error to user if missing.
def extract_param(param):
    def _outer(f):
        @wraps(f)
        def _inner(*args, **kwargs):
            value = request.form.get(param)
            if value is None:
                return error_message(f"Missing parameter {param} in request.")
            kwargs[param] = value
            return f(*args, **kwargs)

        return _inner

    return _outer


@app.errorhandler(OpenStackError)
def handle_openstack_error(err):
    return jsonify({"message": err.message, "errors": [str(err.cause())]}), 500


@app.errorhandler(RcloneError)
def handle_rclone_error(err):
    return jsonify({"message": err.message, "errors": [str(err.__context__)]}), 500


# Helper function for simplifying returning an error message with possible root causes.
def error_message(
    message, exit_code=400, errors=[], added=None, removed=None, backup=None
):
    # added, remoted, backup included for cases where there is a partial success, i.e. adding all remotes.
    data = {
        "message": message,
        "errors": errors,
        "added": added,
        "removed": removed,
        "backup": backup,
    }
    return jsonify({k: v for k, v in data.items() if v is not None}), exit_code


def changed_remotes(added=None, removed=None, backup=None):
    data = {"added": added, "removed": removed, "backup": backup}
    return jsonify({k: v for k, v in data.items() if v is not None}), 200


@app.route("/")
def index():
    return "", 200


# Add a new S3 or Swift Allas remote for a project.
@app.route("/add", methods=["POST"])
@extract_param("project")
@extract_param("remote_type")
@requires_auth
def add(os_token=None, project=None, remote_type=None):
    projects = get_projects(os_token)

    project = next(
        (p for p in projects if p["Name"] == project or p["ID"] == project),
        None,
    )
    if project is None:
        return error_message("Invalid project name or ID")
    remote = None
    backup_file = None

    if remote_type == "s3":
        token = get_or_create_s3_token(os_token, project["ID"])
        remote, backup_file = add_rclone_s3_conf(
            project["Name"], token["Access"], token["Secret"]
        )
    elif remote_type == "swift":
        swift_token = create_scoped_token(os_token, project["ID"])
        storage_account = get_storage_account(swift_token, project["ID"])
        remote, backup_file = add_rclone_swift_conf(
            project["Name"], storage_account, swift_token["id"]
        )
    return changed_remotes(added=[remote], backup=backup_file)


# Add (Swift) remotes for all Allas projects.
@app.route("/add_all", methods=["POST"])
@extract_param("remote_type")
@requires_auth
def add_all(os_token=None, remote_type=None):
    # Disallow generating S3 for all for now.
    if remote_type != "swift":
        return error_message(
            f"Can not create all remotes for remote type {remote_type}", 401
        )
    projects = get_projects(os_token)
    if len(projects) == 0:
        return error_message("No projects found.", 500)
    conf = None
    errors = []
    added = []
    for project in projects:
        try:
            swift_token = create_scoped_token(os_token, project["ID"])
            storage_account = get_storage_account(swift_token, project["ID"])
            remote, conf = backup_file = add_rclone_swift_conf(
                project["Name"],
                storage_account,
                swift_token["id"],
                conf=conf,
                write=False,
            )
            added.append(remote)
        except OpenStackError as err:
            errors.append(
                f"Could not add remote for {project['Name']}:\n{err.full_message()}"
            )
    backup_file = None
    if not conf is None:
        backup_file = write_rclone_conf(conf)
    if len(errors) > 0:
        return error_message(
            f"Configuration for one or more remotes failed",
            500,
            errors,
            added=added,
            backup=backup_file,
        )
    return changed_remotes(added=added, backup=backup_file)


# Copy configuration for either a project or an already known list of remotes to the normal Rclone config.
def add_lumio(project=None, remotes=None):
    errors = []

    errors = (
        json.loads(base64.b64decode(unquote(request.cookies.get("lumio-errors")))).get(
            "errors", []
        )
        if "lumio-errors" in request.cookies
        else []
    )
    errors = list(map(lambda e: escape(e), errors))

    remotes = (
        remotes
        if project is None
        else [f"lumi-{project}-private", f"lumi-{project}-public"]
    )

    remotes, backup_file = copy_lumio_remotes(remotes)

    # Rails forms always sends the form value for checkboxes as a an array where the last one is the real one.
    s3cmd = request.form.getlist("s3cmd")
    if len(s3cmd) and s3cmd[-1] == "1" and len(remotes):
        remote = remotes[0]
        project = (
            remote.removeprefix("lumi-")
            .removesuffix("-public")
            .removesuffix("-private")
        )
        access_key = get_remote_option(remote, "access_key_id")
        secret = get_remote_option(remote, "secret_access_key")
        if access_key and secret:
            configure_s3cmd(project, access_key, secret)

    if len(errors) > 0:
        res = make_response(
            error_message(
                "",
                500,
                errors,
                added=remotes,
                backup=backup_file,
            )
        )
        res.delete_cookie("lumio-errors")
        return res
    return changed_remotes(added=remotes, backup=backup_file)


# Copy LUMI-O remotes for a project from the lumio Rclone config to the normal config.
@app.route("/add_lumio", methods=["POST"])
@extract_param("project")
def add_single_lumio(project=None):
    return add_lumio(project=project)


# Copy all LUMI-O remotes from the LUMI-O Rclone config to the normal config.
@app.route("/add_all_lumio", methods=["POST"])
def add_all_lumio():
    return add_lumio(remotes=lumio_remotes())


# Delete a remote from the Rclone config.
@app.route("/delete", methods=["POST"])
@extract_param("remote")
def delete_project(remote=None):
    backup_file = delete_rclone_remote(remote)
    return changed_remotes(removed=[remote], backup=backup_file)


# Delete a lumio remotes for a project from the Rclone config.
@app.route("/delete_lumio", methods=["POST"])
@extract_param("remote")
def delete_lumio_remote(remote=None):
    # Attempt to extract project from remote name (e.g. lumi-123456-public). Assume remote name is already project if it fails.
    m = re.search(r"lumi-(\d+)-p", remote)
    project = m.groups()[0] if m and m.groups()[0] else remote

    remotes = [f"lumi-{project}-private", f"lumi-{project}-public"]
    backup_file = delete_rclone_remote(remotes)
    return changed_remotes(removed=remotes, backup=backup_file)


# Revoke an Allas remote and delete it from the Rclone config.
@app.route("/revoke", methods=["POST"])
@extract_param("remote")
@requires_auth
def revoke_remote(os_token=None, remote=None):
    remotes = list_remotes()
    remote = next(
        (r for r in remotes if r["name"] == remote),
        None,
    )
    if remote is None:
        return error_message("Remote does not exist.")
    if remote["type"] == "swift":
        auth_token = get_remote_option(remote["name"], "auth_token")
        if auth_token is None:
            return error_message("Remote does not have a token to revoke.")
        storage_url = get_remote_option(remote["name"], "storage_url")
        if storage_url is None or not OS_STORAGE_URL_BASE in storage_url:
            return error_message(
                "Access token for remote can not be revoked as it is not an Allas access token."
            )
        revoke_token(auth_token)
    elif remote["type"] == "s3":
        s3_token_id = get_remote_option(remote["name"], "access_key_id")
        if s3_token_id is None:
            return error_message("Remote does not have an access token.")

        # Need the ID of any project to list S3 tokens.
        any_project = next(iter(get_projects(os_token)), None)
        if any_project is None:
            return error_message("No valid projects found for user.", 500)

        s3_tokens = get_s3_tokens(os_token, any_project["ID"])
        s3_token = next(
            (t for t in s3_tokens if t["Access"] == s3_token_id),
            None,
        )
        # Token is valid and is for Allas. Revoke it.
        if not s3_token is None:
            project_id = s3_token["Project ID"]
            delete_s3_token(os_token, project_id, s3_token_id)
        elif (
            get_remote_option(remote["name"], "endpoint")
            != RCLONE_BASE_S3_CONF["endpoint"]
        ):
            return error_message(
                f"Access token for remote can not be revoked as it is not an Allas access token."
            )
    else:
        return error_message(
            f"Access tokens for remotes of type {remote['type']} can not be revoked."
        )
    backup_file = delete_rclone_remote(remote["name"])
    return changed_remotes(removed=[remote["name"]], backup=backup_file)


@app.get("/projects")
@requires_auth
def projects(os_token=None):
    projects = get_projects(os_token)
    return jsonify(projects)


@app.get("/remotes")
def remotes():
    remotes = list_remotes()
    # Add expiration time to Allas Swift remotes
    for remote in remotes:
        if remote["type"] != "swift":
            continue
        auth_token = get_remote_option(remote["name"], "auth_token")
        if auth_token is None:
            continue
        storage_url = get_remote_option(remote["name"], "storage_url")
        if storage_url is None or not OS_STORAGE_URL_BASE in storage_url:
            continue
        try:
            token_info = get_token_info(auth_token)
            if token_info.get("error", {}).get("code") == 401:
                remote["expires"] = "Expired"
                continue
            expires = token_info.get("token", {}).get("expires_at")
            if not expires is None:
                remote["expires"] = int(parse_expires(expires).strftime("%s"))
        except Exception:
            # Silently ignore all exceptions, expiry info is not important.
            pass
    return jsonify(remotes)


# Returns the expiry time of the current openstack token.
@app.get("/status")
@requires_auth
def status(os_token=None):
    return (
        jsonify({"expires": int(os_token["expires"].strftime("%s"))}),
        200,
    )


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
            errors.append(err.full_message())
        except RcloneError as err:
            errors.append(err.full_message())
    if len(errors):
        return error_message("One or more tokens could not be revoked", 500, errors)
    return jsonify({}), 200


@app.route("/renew_token", methods=["POST"])
@extract_param("password")
def renew_token(password=None):
    os_token = get_unscoped_token(password)
    save_os_token(os_token)
    return jsonify({}), 200


if __name__ == "__main__":
    app.run()
