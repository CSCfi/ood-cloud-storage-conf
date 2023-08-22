from flask import Flask, render_template, request
import os
import sys
import subprocess
from shlex import quote

app = Flask(__name__)

@app.route("/")
def index():
    return '', 200

@app.route("/auth", methods=["POST"])
def auth():
    try:
        password = request.form["password"]
        project = request.form["project"]

        bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")

        cmd = f"bash -c 'allas-conf -f -s -k -m s3 -p {quote(project)}'"

        env = os.environ.copy()
        env["PATH"] += f":{bin_dir}"
        env["OS_PASSWORD"] = password

        res = subprocess.run(cmd, shell=True, env=env, stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True)

        if res.returncode != 0:
            return f"Internal server error: {res.stdout}\n{res.stderr}", 500
        else:
            return f"{res.stdout}\n{res.stderr}", 200
    except Exception as e:
        return f"Internal server error: {e}", 500

if __name__ == '__main__':
    app.run()
