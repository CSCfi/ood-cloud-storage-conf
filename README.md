# Allas configuration tool

A Passenger app and custom dashboard page for configuring Rclone remotes with access to Allas using S3.
Remotes are named according to the project name with the format `allas-<project>`.
Remotes that are not for Allas can be deleted but not revoked.


The user logs in to the app using their CSC password.
This generates and unscoped OpenStack (OS) token with a lifetime of 8h that is used for subsequent requests.
These OS tokens are not visible to the user anywhere.
Without authentication the user can list and delete any Rclone remotes they have configured.

The custom dashboard page is in the ood-initializers repo as a widget, with a custom dashboard page configured in `ondemand.d/dashboard.yml.erb`.
The backend is as an API using Python with Flask.


## Frontend

The frontend is implemented as a widget on a custom dashboard page.
The backend API is used in the background to avoid extra page loads.

Refreshing the list of remotes in OOD requires running the relevant initializers again, which the custom dashboard page does if the parameter `refresh` is defined.
Currently the refreshing happens in the background, as the updated list of remotes is only visible after an additional page load.
The updated list of remotes is added temporarily using JavaScript until the user reloads the page again.

Error messages are directly propagated from the underlying backend API with some context added to describe what was attempted.


## Backend

The backend is a Python Flask app.
`python-openstackclient` is used for generating both the internal OS token, and the S3 tokens used by Rclone in OOD.
Rclone is not used directly anywhere, instead the `configparser` module is used for modifying the `rclone.conf` file.

The user's password is used to generate an unscoped (valid for all projects) OS token for internal use, stored under `/tmp/$USER/os-token.*`, with a lifetime of 8h.
Expired tokens are automatically cleaned up.
The user can revoke their existing tokens earlier using the `/revoke_tokens` endpoint, which revokes and deletes all authentication tokens that are used internally.

The S3 tokens generated for remotes have no expiry, and must be manually revoked by the user.
`allas-conf` currently reuses S3 tokens, so any tokens revoked may be in use elsewhere.

The default Rclone config file at `$HOME/.config/rclone/rclone.conf` is used for saving and loading the Rclone remotes.
The `configparser` module does not support comments in the configuration files, and does not guarantee the order of the configuration items.
If comments are found in the `rclone.conf` file, it is backed up and the name of the backup file is shown to the user.


### API Endpoints

#### `GET /` - health check  


#### `GET /status` - current status of authentication  


#### `POST /revoke_tokens` - revoke authentication (internal token)  


#### `POST /renew_token` - renew the current authentication (new internal token)  
Form parameters:
- `password: string` - the users' password


#### `GET /projects` - get user projects  
Requires auth.


#### `GET /remotes` - get Rclone remotes  


#### `POST /add` - add/generate new Rclone remote for project  
Requires auth.
Form parameters:
- `project: string` - project name or ID


#### `POST /delete` - delete a Rclone remote  
Form parameters:
- `remote: string` - the name of the Rclone remote


#### `POST /revoke_remote` - revoke access token for Rclone remote and delete it  
Requires auth.
Form parameters:
- `remote: string` - the name of the Rclone remote

