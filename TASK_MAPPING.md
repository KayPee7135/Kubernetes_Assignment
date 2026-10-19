# Assignment tasks mapped to files and commands

Student ID: `02230130`  
Namespace: `usermgmt-02230130`  
Ingress host: `usermgmt-02230130.local`  
Platform: Docker Desktop, Windows PowerShell, minikube, and Git Bash for VPA setup

Run PowerShell commands from `D:\ITM403\Assignment`, unless the step says Git Bash. For each task below, the matching project file and command are listed directly under it.

## Before the milestones — required tools

Start Docker Desktop. If Git is already installed, install minikube and kubectl from Administrator PowerShell:

```powershell
winget install -e --id Kubernetes.minikube
winget install -e --id Kubernetes.kubectl
```

Close and reopen PowerShell, then check the tools:

```powershell
docker version
git --version
minikube version
kubectl version --client
```

## Milestone 1 — Cluster and platform setup

### Task: Start minikube with at least 2 CPUs and 4 GB memory

**Use:** Docker Desktop must be running with Linux containers.

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
kubectl get nodes
```

### Task: Enable Ingress and metrics-server

**Use:** Traefik, matching `ingressClassName: traefik` in `k8s/06-ingress.yaml`. This add-on requires minikube 1.39.0 or later.

```powershell
minikube addons enable metrics-server
minikube addons enable traefik
kubectl get ingressclass
kubectl get pods -A
kubectl top nodes
```

### Task: Install the Vertical Pod Autoscaler components

**Use:** Git Bash, from a folder outside this repository. The script installs the cluster platform component.

```bash
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
kubectl get pods -n kube-system | grep vpa
```

Wait until the recommender, updater, and admission-controller Pods show `Running`:

```powershell
kubectl get pods -A
```

### Task: Create the SID-specific namespace from a manifest

**File:** `k8s/01-namespace.yaml` defines `usermgmt-02230130`.

```powershell
kubectl apply -f .\k8s\01-namespace.yaml
kubectl get namespace usermgmt-02230130
```

### Task: Identify the default StorageClass and provisioner

```powershell
kubectl get storageclass
kubectl get storageclass standard -o yaml
```

The default class is marked `(default)` in the first command. Read its `provisioner` field in the YAML output. If the class has a different name, substitute that name in the second command.

### Evidence for Milestone 1

Capture the output of `kubectl get nodes`, `kubectl get pods -A`, `kubectl get storageclass`, and `kubectl top nodes`.

## Milestone 2 — Stateful PostgreSQL database

### Task: Create a Secret for database name, username, and password

**File:** `scripts/New-DbSecret.ps1` asks for a password and generates `k8s/02-db-secret.yaml`. The generated Secret is ignored by Git. Database and username are both `usermgmt`.

```powershell
.\scripts\New-DbSecret.ps1
kubectl apply -f .\k8s\02-db-secret.yaml
kubectl get secret postgres-secret -n usermgmt-02230130
```

Do not commit the generated Secret. Base64 values in a Kubernetes Secret are not encryption.

### Task: Create a headless Service named postgres

**File:** `k8s/03-postgres.yaml` contains the Service with `clusterIP: None` and port `5432`.

```powershell
kubectl apply -f .\k8s\03-postgres.yaml
kubectl get service postgres -n usermgmt-02230130
```

### Task: Create a one-replica PostgreSQL StatefulSet using Secret credentials

**File:** `k8s/03-postgres.yaml` defines the `postgres` StatefulSet and reads all three PostgreSQL values from `postgres-secret`.

```powershell
kubectl rollout status statefulset/postgres -n usermgmt-02230130 --timeout=180s
kubectl get statefulset,pod -n usermgmt-02230130
```

Expected Pod name: `postgres-0`.

### Task: Give the StatefulSet a per-Pod PVC of at least 1 Gi

**File:** In `k8s/03-postgres.yaml`, `volumeClaimTemplates` requests `1Gi` with `ReadWriteOnce`.

```powershell
kubectl get pvc,pv -n usermgmt-02230130
```

### Task: Set database resource requests and limits

**File:** In the same StatefulSet container, `resources.requests` are `100m` CPU and `256Mi` memory; limits are `500m` CPU and `512Mi` memory.

```powershell
kubectl describe pod postgres-0 -n usermgmt-02230130
```

### Task: Prove that data survives deletion of postgres-0

Run this in PowerShell to create and read one row:

```powershell
@'
CREATE TABLE IF NOT EXISTS persistence_check (id SERIAL PRIMARY KEY, note TEXT NOT NULL);
INSERT INTO persistence_check (note) VALUES ('sid-02230130-persisted');
SELECT * FROM persistence_check ORDER BY id DESC LIMIT 1;
'@ | kubectl exec -i -n usermgmt-02230130 postgres-0 -- psql -U usermgmt -d usermgmt
```

Delete the Pod, wait for its replacement, and query the same row:

```powershell
kubectl delete pod postgres-0 -n usermgmt-02230130
kubectl wait --for=condition=Ready pod/postgres-0 -n usermgmt-02230130 --timeout=180s
@'
SELECT * FROM persistence_check ORDER BY id DESC LIMIT 1;
'@ | kubectl exec -i -n usermgmt-02230130 postgres-0 -- psql -U usermgmt -d usermgmt
kubectl get statefulset,pod,pvc,pv -n usermgmt-02230130
```

The row should still appear after the Pod is recreated. Save output from before deletion and after recreation.

## Milestone 3 — User management API

### Task: Write the REST API and store user records in PostgreSQL

**File:** `app/main.py` implements `GET /users`, `POST /users`, `GET /users/{id}`, `PUT /users/{id}`, `DELETE /users/{id}`, `GET /healthz`, and `GET /ready`. The ready endpoint checks the database. Database settings come from environment variables; the password is not in the source code.

### Task: Write a Dockerfile, build a versioned image, and load it into minikube

**Files:** `app/Dockerfile`, `app/requirements.txt`, and `app/main.py`.

```powershell
docker build -t usermgmt-api:1.0 .\app
minikube image load usermgmt-api:1.0
```

Keep the tag `1.0`; do not use `latest`.

### Task: Create a ConfigMap for non-secret database settings

**File:** `k8s/04-api-config.yaml` sets `DB_HOST=postgres`, port `5432`, database name, and username.

```powershell
kubectl apply -f .\k8s\04-api-config.yaml
kubectl get configmap api-config -n usermgmt-02230130 -o yaml
```

### Task: Deploy two API replicas, reading config from ConfigMap and password from Secret

**File:** `k8s/05-api.yaml` references `api-config` and the `DB_PASSWORD` key in `postgres-secret`.

```powershell
kubectl apply -f .\k8s\05-api.yaml
kubectl rollout status deployment/api -n usermgmt-02230130 --timeout=180s
kubectl get deploy,rs,pods -n usermgmt-02230130
```

### Task: Add liveness and readiness probes

**File:** `k8s/05-api.yaml` uses `/healthz` for liveness and `/ready` for readiness. `/ready` returns success only when PostgreSQL responds.

```powershell
kubectl describe deployment api -n usermgmt-02230130
```

### Task: Set API requests and limits

**File:** `k8s/05-api.yaml` requests `100m` CPU and `128Mi` memory; limits are `500m` CPU and `256Mi` memory. The CPU request is needed for HPA utilization calculations.

### Task: Create a ClusterIP Service named api

**File:** `k8s/05-api.yaml` also creates the `api` Service on port `80` targeting container port `8080`.

```powershell
kubectl get service api -n usermgmt-02230130
```

### Task: Demonstrate all CRUD endpoints through port-forward

In a second PowerShell window, start the port-forward and leave it running:

```powershell
kubectl port-forward -n usermgmt-02230130 svc/api 8080:80
```

In the first window, run each endpoint. The created ID is stored in `$created.id` and reused in the later calls.

```powershell
$base = 'http://127.0.0.1:8080'
$created = Invoke-RestMethod -Method Post -Uri "$base/users" -ContentType 'application/json' -Body '{"name":"SID 02230130 User","email":"sid02230130@example.test"}'
$created
Invoke-RestMethod -Method Get -Uri "$base/users"
Invoke-RestMethod -Method Get -Uri "$base/users/$($created.id)"
Invoke-RestMethod -Method Put -Uri "$base/users/$($created.id)" -ContentType 'application/json' -Body '{"name":"Updated SID 02230130 User","email":"updated02230130@example.test"}'
Invoke-RestMethod -Method Delete -Uri "$base/users/$($created.id)"
```

### Evidence for Milestone 3

```powershell
kubectl get deploy,rs,pods,svc -n usermgmt-02230130
```

Capture the Dockerfile, manifests, and successful response for every CRUD call.

## Milestone 4 — Ingress and host routing

### Task: Route usermgmt-02230130.local to Service api

**File:** `k8s/06-ingress.yaml` sends the `/` path to Service `api` on port `80`.

### Task: Set ingressClassName to match the installed controller

The setup above uses Traefik. Check its class and apply the manifest:

```powershell
kubectl get ingressclass
kubectl apply -f .\k8s\06-ingress.yaml
kubectl describe ingress -n usermgmt-02230130
```

If you chose the minikube ingress add-on instead, change `ingressClassName` in the manifest to `nginx` before applying it.

### Task: Add the host name to Windows hosts file

Start the tunnel in a separate elevated PowerShell window and leave it running:

```powershell
minikube tunnel
```

Open `C:\Windows\System32\drivers\etc\hosts` as Administrator and add:

```text
127.0.0.1 usermgmt-02230130.local
```

### Task: Show that the correct host works and a different host does not

```powershell
curl.exe -i http://usermgmt-02230130.local/users
curl.exe -i -H "Host: other.local" http://127.0.0.1/users
```

The first request should reach the API. The second should return the Ingress controller's default 404. Save both results and the hosts file line.

### Evidence for Milestone 4

Capture `kubectl describe ingress -n usermgmt-02230130`, the hosts-file entry, the successful expected-host response, and the other-host failure.

## Milestone 5 — Metrics, HPA, and VPA

### Task: Confirm pod metrics are available

```powershell
kubectl top pods -n usermgmt-02230130
```

### Task: Create an HPA for api with 2–6 replicas and 50% CPU target

**File:** `k8s/07-hpa.yaml` defines `autoscaling/v2`, min replicas `2`, max replicas `6`, and average CPU utilization `50%`.

```powershell
kubectl apply -f .\k8s\07-hpa.yaml
kubectl get hpa -n usermgmt-02230130
```

### Task: Generate load and record replica count during and after the load

In one terminal, run the assignment load command for three minutes:

```powershell
hey -z 3m -c 50 http://usermgmt-02230130.local/users
```

In another PowerShell window, start a transcript and record HPA and Deployment state every 30 seconds. Leave the loop running for several minutes after the load finishes, then press Ctrl+C and run `Stop-Transcript`.

```powershell
Start-Transcript -Path .\hpa-timeline.txt -Append
while ($true) {
  Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  kubectl get hpa api -n usermgmt-02230130
  kubectl get deployment api -n usermgmt-02230130
  Start-Sleep -Seconds 30
}
Stop-Transcript
```

Use the transcript output to make a report timeline showing time, HPA CPU, and desired/current replicas during load and scale-down.

### Task: Create VPA for postgres with updateMode Off and record its recommendations

**File:** `k8s/08-vpa.yaml` targets the PostgreSQL StatefulSet with `updateMode: "Off"`.

```powershell
kubectl apply -f .\k8s\08-vpa.yaml
kubectl describe vpa postgres -n usermgmt-02230130
```

Capture the VPA target, lower bound, and upper bound from the output after the load run.

### Report question: Why put VPA on postgres and use Off mode?

Use this answer in your own words: HPA changes the number of API Pods based on CPU utilization. VPA can change CPU requests, which changes the utilization percentage HPA observes if both act on the same Deployment. This setup puts VPA on PostgreSQL and leaves it in `Off` mode, so it reports resource recommendations without changing or restarting the database Pod during the demonstration.

### Evidence for Milestone 5

Capture `kubectl top pods`, the HPA/VPA manifests, `hpa-timeline.txt`, and `kubectl describe vpa postgres -n usermgmt-02230130`.

## Milestone 6 — Report and demonstration

### Task: Submit a report up to 8 pages, excluding manifest appendix

Include an architecture diagram, evidence for each milestone, and one real issue you diagnosed. For troubleshooting, record the command and actual output, for example:

```powershell
kubectl describe pod <pod-name> -n usermgmt-02230130
kubectl logs <pod-name> -n usermgmt-02230130
kubectl get events -n usermgmt-02230130 --sort-by=.lastTimestamp
```

Use a problem you encountered; do not invent one. Put full YAML manifests in the appendix.

### Task: Demonstrate the application and answer questions

Be ready to explain:

- StatefulSet stable identity and why its PVC survives Pod deletion.
- What happens to the PVC after deleting the StatefulSet or namespace.
- Why API Pods become unready while PostgreSQL is unavailable.
- Why HPA needs CPU requests.
- How traffic flows: client → Ingress controller → host/path rule → Service → ready Pod.
- Why HPA targets api while VPA only recommends values for postgres.

### Task: Submit repository, PDF report, and attend demonstration

The repository should contain `app/`, numbered `k8s/` manifests, the Secret-generation script, and this task mapping/README. Do not commit `k8s/02-db-secret.yaml` because it contains your local password. After preserving evidence, test the README from a clean namespace:

```powershell
kubectl delete namespace usermgmt-02230130
```

Then follow the deployment steps from the beginning. Namespace deletion also deletes its PVC and data.
