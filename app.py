from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from kubernetes import client, config
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "super-secret-key")


try:
    config.load_kube_config()
except:
    config.load_incluster_config()

v1 = client.CoreV1Api()

USERNAME = os.environ.get("APP_USERNAME", "admin")
PASSWORD = os.environ.get("APP_PASSWORD", "admin123")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Hatalı kullanıcı adı veya şifre!")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route('/')
@login_required
def index():
    namespaces = v1.list_namespace().items
    return render_template('index.html', namespaces=namespaces)

@app.route('/pods/<namespace>', methods=['GET'])
@login_required
def list_pods(namespace):
    pods = v1.list_namespaced_pod(namespace) if namespace else []
    pod_names = [pod.metadata.name for pod in pods.items]
    return jsonify(pod_names)

@app.route('/logs/<namespace>/<pod>', methods=['GET'])
@login_required
def get_logs(namespace, pod):
    container_name = request.args.get('container', None)
    tail_lines = request.args.get('tail', 500)
    since_seconds = request.args.get('since', None)
    grep_filter = request.args.get('grep', None)

    try:
        logs = v1.read_namespaced_pod_log(
            name=pod,
            namespace=namespace,
            container=container_name,
            tail_lines=int(tail_lines) if tail_lines else None,
            since_seconds=int(since_seconds) if since_seconds else None,
            timestamps=True
        )

        if grep_filter:
            logs = "\n".join([line for line in logs.splitlines() if grep_filter in line])

        return jsonify({'logs': logs})
    except client.exceptions.ApiException as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)