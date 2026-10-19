# User Management API on Kubernetes

Assignment walkthrough for SID `02230130`, using Docker Desktop on Windows and minikube. The Kubernetes objects for the application are in `k8s/` and are applied with `kubectl apply -f`. The password manifest is generated locally by a PowerShell script and is excluded from Git.

For the assignment reorganized line by line, see [TASK_MAPPING.md](TASK_MAPPING.md). It pairs each task with its file, command, code, or evidence requirement.

## Architecture

```text
Browser / curl (usermgmt-02230130.local)
        -> Traefik Ingress -> api ClusterIP Service -> 2-6 API Pods
                                                    -> postgres headless Service
                                                       -> postgres-0 StatefulSet Pod
                                                          -> 1 Gi persistent volume
```

The API Deployment is managed horizontally by HPA. VPA recommends database resource values in `Off` mode, so it does not change the StatefulSet's Pod resources. This avoids HPA and VPA changing CPU requests for the same workload.

## Prerequisites

Install Docker Desktop, Git for Windows (including Git Bash), `kubectl`, and minikube. If you already have Docker Desktop and Git, install the two Kubernetes tools from an administrator PowerShell window with:

```powershell
winget install -e --id Kubernetes.minikube
winget install -e --id Kubernetes.kubectl
```

Close and reopen PowerShell after installation, then check the tools and Docker Desktop:

```powershell
docker version
minikube version
kubectl version --client
git --version
```

Start Docker Desktop and use Linux containers. The assignment recommends at least 8 GB RAM, 2 free CPU cores, and 20 GB free disk. Use PowerShell for commands below except where Git Bash is called out.

## Deploy from scratch

Run commands from the repository root.

### 1. Start the local cluster and platform components

```powershell
minikube start --driver=docker --cpus=2 --memory=4096
minikube addons enable metrics-server
minikube addons enable traefik
kubectl get nodes
kubectl get storageclass
kubectl top nodes
```

This uses the Traefik add-on and therefore expects minikube 1.39.0 or later. Check that its class is named `traefik` before applying `k8s/06-ingress.yaml`:

```powershell
kubectl get ingressclass
```

Install VPA with Git Bash (use a separate terminal; `cd` to a folder outside this repository if desired):

```bash
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
kubectl get pods -n kube-system | grep vpa
```

Wait until the recommender, updater, and admission-controller Pods are Running:

```powershell
kubectl get pods -A
```

### 2. Create the namespace and local Secret manifest

```powershell
kubectl apply -f .\k8s\01-namespace.yaml
.\scripts\New-DbSecret.ps1
kubectl apply -f .\k8s\02-db-secret.yaml
```

The script prompts for a database password without echoing it. It writes a Kubernetes Secret manifest containing base64 encoded values. Kubernetes Secrets are not encrypted just because the values are base64 encoded; keep this generated file out of Git. The database name and username are both `usermgmt`.

### 3. Deploy PostgreSQL and prove persistence

```powershell
kubectl apply -f .\k8s\03-postgres.yaml
kubectl rollout status statefulset/postgres -n usermgmt-02230130 --timeout=180s
kubectl get statefulset,pod,pvc,pv -n usermgmt-02230130
```

Insert and read a row, delete the Pod, wait for its replacement, and read the row again:

```powershell
@'
CREATE TABLE IF NOT EXISTS persistence_check (id SERIAL PRIMARY KEY, note TEXT NOT NULL);
INSERT INTO persistence_check (note) VALUES ('sid-02230130-persisted');
SELECT * FROM persistence_check ORDER BY id DESC LIMIT 1;
'@ | kubectl exec -i -n usermgmt-02230130 postgres-0 -- psql -U usermgmt -d usermgmt
kubectl delete pod postgres-0 -n usermgmt-02230130
kubectl wait --for=condition=Ready pod/postgres-0 -n usermgmt-02230130 --timeout=180s
@'
SELECT * FROM persistence_check ORDER BY id DESC LIMIT 1;
'@ | kubectl exec -i -n usermgmt-02230130 postgres-0 -- psql -U usermgmt -d usermgmt
```

Keep the command output and capture screenshots for the report.
### 4. Build and deploy the API

```powershell
docker build -t usermgmt-api:1.0 .\app
minikube image load usermgmt-api:1.0
kubectl apply -f .\k8s\04-api-config.yaml
kubectl apply -f .\k8s\05-api.yaml
kubectl rollout status deployment/api -n usermgmt-02230130 --timeout=180s
kubectl get deploy,rs,pods,svc -n usermgmt-02230130
```

### 5. Demonstrate all CRUD routes

Open a second PowerShell window and keep this running:

```powershell
kubectl port-forward -n usermgmt-02230130 svc/api 8080:80
```

In the first window, run the CRUD requests. Save the returned `id` from POST and substitute it for `1` below if it differs:

```powershell
$base = 'http://127.0.0.1:8080'
$created = Invoke-RestMethod -Method Post -Uri "$base/users" -ContentType 'application/json' -Body '{"name":"SID 02230130 User","email":"sid02230130@example.test"}'
$created
Invoke-RestMethod -Method Get -Uri "$base/users"
Invoke-RestMethod -Method Get -Uri "$base/users/$($created.id)"
Invoke-RestMethod -Method Put -Uri "$base/users/$($created.id)" -ContentType 'application/json' -Body '{"name":"Updated SID 02230130 User","email":"updated02230130@example.test"}'
Invoke-RestMethod -Method Delete -Uri "$base/users/$($created.id)"
```

### 6. Configure Ingress on Windows

Run a separate elevated PowerShell terminal and keep the tunnel running while you test the hostname:

```powershell
minikube tunnel
```

As instructed for Windows with Docker Desktop, add this line to `C:\Windows\System32\drivers\etc\hosts` using an administrator editor:

```text
127.0.0.1 usermgmt-02230130.local
```

Apply and inspect the Ingress:

```powershell
kubectl apply -f .\k8s\06-ingress.yaml
kubectl describe ingress -n usermgmt-02230130
curl.exe -i http://usermgmt-02230130.local/users
curl.exe -i -H "Host: other.local" http://127.0.0.1/users
```

The final request should return the Ingress controller's default 404, not the API response. If it does not, confirm `kubectl get ingressclass`, `kubectl get pods -A`, `kubectl get ingress -n usermgmt-02230130`, that the tunnel is still running, and that Windows resolved the hostname with `ping usermgmt-02230130.local`.

### 7. HPA and VPA

```powershell
kubectl top pods -n usermgmt-02230130
kubectl apply -f .\k8s\07-hpa.yaml
kubectl apply -f .\k8s\08-vpa.yaml
kubectl get hpa,vpa -n usermgmt-02230130
```

Install `hey` for Windows or use an equivalent load generator. In one terminal, run:

```powershell
hey -z 3m -c 50 http://usermgmt-02230130.local/users
```

While it runs, record HPA state and replica count every 30 seconds. Leave it running for several minutes after `hey` ends to capture scale-down. In another terminal:

```powershell
Start-Transcript -Path .\hpa-timeline.txt -Append
while ($true) {
  Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  kubectl get hpa api -n usermgmt-02230130
  kubectl get deployment api -n usermgmt-02230130
  kubectl get pods -n usermgmt-02230130 -l app=api
  Start-Sleep -Seconds 30
}
```

Stop the loop with Ctrl+C after the load and scale-down period, then end the transcript:

```powershell
Stop-Transcript
```

Capture output/screenshots and summarize the time and desired/current replicas in a report table. Then inspect the database recommendation:

```powershell
kubectl describe vpa postgres -n usermgmt-02230130
```

Explain that VPA observes the database and provides sizing recommendations while `Off` avoids evicting/recreating the database Pod or changing its requests during the assignment. HPA adjusts API replica count based on CPU utilization as a percentage of each Pod's CPU request. If VPA changed those same API requests, it could change the utilization denominator and work against HPA; this design assigns VPA to PostgreSQL instead.

### 8. Evidence and repository

Capture these outputs/screenshots for your report:

- `kubectl get nodes`, `kubectl get pods -A`, `kubectl get storageclass`, and `kubectl top nodes`.
- `kubectl get statefulset,pod,pvc,pv -n usermgmt-02230130` plus the successful persistence query before and after Pod deletion.
- `kubectl get deploy,rs,pods,svc -n usermgmt-02230130` and successful POST, list, get-one, update, and delete responses.
- `kubectl describe ingress -n usermgmt-02230130`, the hosts file line, successful correct-host request, and failing other-host request.
- `kubectl top pods`, HPA/Pod timeline under load and after load, and `kubectl describe vpa postgres -n usermgmt-02230130`.
- One genuine troubleshooting example from your run: capture a failing `kubectl describe`, `kubectl logs`, or `kubectl get events` output and explain the cause and fix.

Commit the source, Dockerfile, numbered manifests, README, and report. Do not commit `k8s/02-db-secret.yaml`; the ignored script regenerates it on a fresh setup. Before final submission, delete the namespace and repeat from this README. Namespace deletion removes its PVC and data, so do this only after preserving the evidence you need:

```powershell
kubectl delete namespace usermgmt-02230130
```

## Design questions for the demonstration

- A StatefulSet gives the database a stable identity (`postgres-0`) and a PVC per replica. A Deployment is designed for interchangeable Pods and does not provide that stable identity.
- Deleting the StatefulSet normally leaves its PVC behind, preserving data; deleting the namespace removes namespaced PVC objects, and the PV reclaim policy then controls underlying storage cleanup.
- When PostgreSQL restarts, the API readiness endpoint fails its database check, so API Pods temporarily stop receiving Service traffic. Their liveness endpoint remains healthy because the process is running.
- HPA needs CPU requests to calculate utilization percentage (measured CPU divided by requested CPU).
- Traffic enters at the Ingress controller; the Ingress host/path rule chooses the Service, which selects ready API Pods.
