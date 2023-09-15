import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from tempfile import NamedTemporaryFile

from .constants import TMPDIR
from .utils import create_private_dir


# Save openstack token to tmpdir.
def save_os_token(token):
    create_private_dir(TMPDIR)
    with NamedTemporaryFile(
        dir=TMPDIR, prefix="os-token.", mode="w+", delete=False
    ) as f:
        json.dump(token, f)


def is_expired(token):
    curr_time = datetime.now(tz=timezone.utc)
    return token["expires"] - curr_time < timedelta(seconds=0)


def parse_expires(expires):
    return datetime.strptime(expires, "%Y-%m-%dT%H:%M:%S%z")


# Gets non-expired openstack tokens.
def get_cached_os_token():
    tokens = []
    # Find non-expired tokens, clean up expired.
    for token_file in glob.glob(f"{TMPDIR}/os-token.*"):
        try:
            expired = False
            with open(token_file) as f:
                token = json.load(f)
                token["expires"] = parse_expires(token["expires"])
                expired = is_expired(token)
                if not expired:
                    tokens.append((token_file, token))
            if expired:
                os.remove(token_file)
        except OSError as err:
            print(f"Error reading token file: {err}", file=sys.stderr)
    tokens.sort(key=lambda e: e[1]["expires"], reverse=True)
    # TODO: Could clean up extra tokens here (they shouldn't exist though).
    return tokens[0][1] if tokens else None

def remove_cached_os_tokens():
    for token_file in glob.glob(f"{TMPDIR}/os-token.*"):
        os.remove(token_file)