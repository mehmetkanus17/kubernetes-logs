# Kubernetes Logs Arayüzü

- Bu proje, Kubernetes cluster'ınızdaki pod loglarını kolayca görüntüleyebilmeniz için basit bir web arayüzü sunar.
- Projenin temel amacı, belirli namespace'lerdeki logları göstermektir.
- Bu repodaki app.py dosyası içerisindeki kısmı, kendi uygulama namespacelerinizle değiştirin.

````python
# İzin verilen namespace'ler. 
ALLOWED_NAMESPACES = ["backend", "backend-dev", "frontend", "frontend-dev"]
````

# İsteğe Bağlı: Cluster Genelinde tüm namespace/logs Görüntüleme Kurulumu için

- Eğer varsayılan, sınırlandırılmış namespace'ler yerine cluster'ınızdaki tüm namespace ve pod'ların loglarını görüntülemek isterseniz, aşağıdaki adımları izleyin.

1. Adım: Yetkilendirme (RBAC)
- Uygulamanın tüm namespace'lerdeki pod loglarını okuyabilmesi için Kubernetes API'sine geniş erişim yetkisi verilmesi gerekir.
- Aşağıdaki RBAC (Role-Based Access Control) konfigürasyonunu cluster'ınıza uygulayın.
- Bu konfigürasyon, logs adında bir ServiceAccount ve bu hesaba cluster genelinde okuma yetkisi veren bir ClusterRole ile ClusterRoleBinding oluşturur.

- 01-rbac.yaml
````yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: logs
  namespace: logs
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: logs-role
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: logs-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: logs-role
subjects:
- kind: ServiceAccount
  name: logs
  namespace: logs
````

2. Adım: Uygulama Kodlarını Güncelleme
- Aşağıdaki app.py ve index.html dosyalarını kendi projenizdeki dosyalarla değiştirin. Bu kodlar, kimlik doğrulama, tüm namespace'leri listeleme ve logları filtreleme özelliklerini içerir.

- app.py
````python
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
````

- index.html
````html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kubernetes Logs App</title>
    <link rel="icon" type="image/png" href="/static/favicon2.ico">
    <style>
        body {
            font-family: sans-serif;
            background: linear-gradient(to bottom right, #283cbb, #8e0e00);
            color: white;
            margin: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            padding: 10px;
        }
        .container {
            background-color: rgba(0, 0, 0, 0.5);
            padding: 10px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);
            max-width: 95%;
            width: 1200px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logout {
            color: white;
            text-decoration: none;
            font-weight: bold;
            background: rgba(255, 255, 255, 0.1);
            padding: 5px 10px;
            border-radius: 5px;
            transition: background 0.3s;
        }
        .logout:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        .namespace-list {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            margin-bottom: 10px;
        }
        .namespace-item {
            padding: 5px 10px;
            margin: 5px;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
            white-space: nowrap;
        }
        .namespace-item:hover {
            background-color: rgba(255, 255, 255, 0.2);
        }
        /* Yeni Pod Listesi Düzenlemesi */
        #pod-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 10px;
            list-style: none;
            padding: 0;
            width: 100%;
        }
        li {
            padding: 5px 10px;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
            text-align: center;
        }
        li:hover {
            background-color: rgba(255, 255, 255, 0.2);
        }
        pre {
            background-color: rgba(0, 0, 0, 0.7);
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            width: 100%;
            max-height: 500px;
            overflow-y: auto;
        }
        h1, h2 {
            text-align: center;
            margin: 10px 0;
        }
        .log-controls {
            margin: 10px 0;
            text-align: center;
        }
        .log-controls select, .log-controls input, .log-controls button {
            margin: 0 5px;
            padding: 5px;
            border-radius: 5px;
            border: none;
        }
        .log-controls button {
            cursor: pointer;
            background: rgba(255,255,255,0.2);
            color: white;
            font-weight: bold;
        }
        .log-controls button:hover {
            background: rgba(255,255,255,0.4);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Kubernetes Logs App</h1>
            <a href="/logout" class="logout">log out</a>
        </div>

        <h2>Namespaces</h2>
        <div class="namespace-list">
            {% for ns in namespaces %}
                <div class="namespace-item" onclick="loadPods('{{ ns.metadata.name }}')">
                    {{ ns.metadata.name }}
                </div>
            {% endfor %}
        </div>

        <h2>Pods</h2>
        <ul id="pod-list"></ul>

        <div class="log-controls">
            <label for="tail">Logs Tail:</label>
            <select id="tail">
                <option value="">All</option>
                <option value="100">100</option>
                <option value="250">250</option>
                <option value="500" selected>500</option>
                <option value="1000">1000</option>
            </select>

            <label for="grep">Filter:</label>
            <input id="grep" type="text" placeholder="e.g.: ERROR">

            <button onclick="reloadLogs()">View Logs</button>
        </div>

        <h2>Logs</h2>
        <pre id="logs"></pre>
    </div>

    <script>
        let currentNamespace = null;
        let currentPod = null;

        async function loadPods(namespace) {
            const response = await fetch(`/pods/${namespace}`);
            const pods = await response.json();
            const podList = document.getElementById('pod-list');
            currentNamespace = namespace;
            podList.innerHTML = pods.map(
                pod => `<li onclick="selectPod('${namespace}', '${pod}')">${pod}</li>`
            ).join('');
        }

        function selectPod(namespace, pod) {
            currentPod = pod;
            getLogs(namespace, pod);
        }

        async function getLogs(namespace, pod) {
            const tail = document.getElementById('tail').value;
            const grep = document.getElementById('grep').value;

            let url = `/logs/${namespace}/${pod}`;
            const params = [];
            if (tail) params.push(`tail=${tail}`);
            if (grep) params.push(`grep=${grep}`);
            if (params.length > 0) url += `?${params.join("&")}`;

            const response = await fetch(url);
            const data = await response.json();
            document.getElementById('logs').textContent = data.logs || data.error;
        }

        function reloadLogs() {
            if (currentNamespace && currentPod) {
                getLogs(currentNamespace, currentPod);
            }
        }
    </script>
</body>
</html>
````

- 01-rbac.yaml
````yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: logs
  namespace: logs
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: logs-role
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: logs-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: logs-role
subjects:
- kind: ServiceAccount
  name: logs
  namespace: logs