# GitOps Kubernetes Với Argo CD, Argo Rollouts Và Monitoring

Repo này demo một hệ thống GitOps chạy trên Kubernetes. Toàn bộ trạng thái mong muốn của hệ thống được khai báo bằng YAML trong Git. Argo CD đọc Git, so sánh với cluster, rồi tự động tạo, cập nhật hoặc xóa tài nguyên để cluster luôn khớp với nội dung trong repo.

Luồng chính:

```text
GitHub main
  -> Argo CD root Application
  -> Argo CD Application con
  -> Kubernetes resources
```

## Thành Phần Chính

Hệ thống hiện tại gồm:

- `root`: Argo CD Application gốc, dùng mô hình app-of-apps.
- `demo-namespace`: tạo namespace `demo`.
- `backend`: service backend demo trả về chuỗi `hello from backend`.
- `frontend`: Nginx frontend serve HTML và proxy `/api/` sang backend.
- `argo-rollouts`: cài Argo Rollouts controller bằng Helm.
- `api`: API demo triển khai bằng Argo Rollouts theo chiến lược canary.
- `kube-prometheus-stack`: cài Prometheus, Grafana, Alertmanager và các CRD monitoring.
- `ServiceMonitor`: cấu hình Prometheus scrape metrics từ API.

## Công Nghệ Được Dùng

| Công nghệ | Dùng để làm gì |
| --- | --- |
| Kubernetes | Chạy container, Deployment, Service, Namespace, ConfigMap |
| Argo CD | GitOps controller, tự đồng bộ cluster theo Git |
| App-of-apps | Cho một Application cha quản lý nhiều Application con |
| Argo Rollouts | Triển khai canary rollout cho API |
| Helm | Cài chart `argo-rollouts` và `kube-prometheus-stack` |
| Prometheus Operator | Cung cấp CRD như `ServiceMonitor` |
| Prometheus | Thu thập metrics |
| Grafana | Hiển thị dashboard |
| Alertmanager | Quản lý cảnh báo |
| Nginx | Chạy frontend và reverse proxy `/api/` |

## Cấu Trúc Repo

```text
.
|-- argocd
|   |-- root.yaml
|   `-- apps
|       |-- namespace.yaml
|       |-- backend.yaml
|       |-- frontend.yaml
|       |-- argo-rollouts.yaml
|       |-- kube-prometheus-stack.yaml
|       `-- api.yaml
|-- k8s
|   |-- base
|   |   `-- namespace.yaml
|   |-- backend
|   |   `-- backend.yaml
|   |-- frontend
|   |   `-- frontend.yaml
|   |-- namespace.yaml
|   `-- web.yaml
|-- k8s-api
|   |-- api.yaml
|   `-- servicemonitor.yaml
|-- app
|   |-- app.py
|   `-- Dockerfile
|-- SYSTEM_FLOW.md
`-- README.md
```

Ghi chú:

- `argocd/root.yaml` là file apply ban đầu để khởi động mô hình app-of-apps.
- `argocd/apps/*` là các Argo CD Application con.
- `k8s/base` tạo namespace nền tảng.
- `k8s/backend` chứa backend demo.
- `k8s/frontend` chứa frontend Nginx.
- `k8s-api` chứa API rollout và ServiceMonitor.
- `k8s/web.yaml` và `k8s/namespace.yaml` là manifest demo độc lập, không phải flow chính của `root` hiện tại.

## Root Application

File:

```text
argocd/root.yaml
```

`root` là Application cha của Argo CD. Nó không tạo trực tiếp Pod, Deployment hay Service. Nó chỉ đọc thư mục:

```yaml
path: argocd/apps
```

Sau đó tạo các Application con nằm trong thư mục này.

Phần quan trọng:

```yaml
spec:
  project: default
  source:
    repoURL: https://github.com/pkhoa011004/github-action-argocd.git
    targetRevision: main
    path: argocd/apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
```

Ý nghĩa:

- `project: default`: Application thuộc AppProject mặc định của Argo CD.
- `repoURL`: repo GitHub mà Argo CD theo dõi.
- `targetRevision: main`: Argo CD đọc nhánh `main`.
- `path: argocd/apps`: thư mục chứa các Application con.
- `destination.server`: cluster Kubernetes nội bộ nơi Argo CD đang chạy.
- `destination.namespace: argocd`: Application object được tạo trong namespace `argocd`.

## Mô Hình App-Of-Apps

Mô hình app-of-apps giúp quản lý nhiều app con từ một app cha.

```text
root Application
|-- demo-namespace Application
|   `-- Namespace demo
|-- backend Application
|   |-- Deployment backend
|   `-- Service backend
|-- frontend Application
|   |-- ConfigMap frontend-html
|   |-- ConfigMap frontend-nginx
|   |-- Deployment frontend
|   `-- Service frontend
|-- argo-rollouts Application
|   `-- Helm chart argo-rollouts
|-- kube-prometheus-stack Application
|   `-- Helm chart kube-prometheus-stack
`-- api Application
    |-- Rollout api
    |-- Service api
    `-- ServiceMonitor api
```

Vì vậy trong UI Argo CD:

- Mở `root` sẽ thấy các Application con.
- Mở `backend` sẽ thấy Deployment, Service và Pod backend.
- Mở `frontend` sẽ thấy ConfigMap, Deployment, Service và Pod frontend.
- Mở `api` sẽ thấy Rollout, Service và ServiceMonitor.

## Thứ Tự Sync

Argo CD dùng annotation `argocd.argoproj.io/sync-wave` để quyết định thứ tự apply.

| Wave | Application | Vai trò |
| --- | --- | --- |
| `-1` | `demo-namespace` | Tạo namespace `demo` trước |
| `0` | `backend` | Tạo backend service |
| `1` | `frontend` | Tạo frontend gọi backend |
| `2` | `argo-rollouts` | Cài controller và CRD Rollout |
| `2` | `kube-prometheus-stack` | Cài Prometheus stack và CRD monitoring |
| `3` | `api` | Tạo API Rollout và ServiceMonitor |

Thứ tự này quan trọng vì:

- Namespace phải có trước resource namespaced.
- Backend nên có trước frontend vì frontend proxy request sang backend.
- Argo Rollouts phải có trước khi tạo `kind: Rollout`.
- kube-prometheus-stack phải có trước khi tạo `kind: ServiceMonitor`.

## Namespace Demo

Application:

```text
argocd/apps/namespace.yaml
```

Manifest Kubernetes:

```text
k8s/base/namespace.yaml
```

Mục đích là tạo namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: demo
```

Các workload ứng dụng như backend, frontend và API đều chạy trong namespace `demo`.

## Backend

Application:

```text
argocd/apps/backend.yaml
```

Manifest:

```text
k8s/backend/backend.yaml
```

Backend gồm:

- `Deployment backend`
- `Service backend`

Deployment chạy image:

```yaml
image: hashicorp/http-echo:1.0
```

Container lắng nghe port `8080` và trả về:

```text
hello from backend
```

Service `backend` tạo DNS nội bộ trong cluster:

```text
backend.demo.svc.cluster.local:8080
```

Frontend dùng địa chỉ này để gọi backend.

## Frontend

Application:

```text
argocd/apps/frontend.yaml
```

Manifest:

```text
k8s/frontend/frontend.yaml
```

Frontend gồm:

- `ConfigMap frontend-html`: chứa file `index.html`.
- `ConfigMap frontend-nginx`: chứa cấu hình Nginx.
- `Deployment frontend`: chạy container Nginx.
- `Service frontend`: tạo service nội bộ cho frontend.

Nginx serve HTML ở route `/`.

Khi browser gọi:

```text
/api/
```

Nginx proxy request sang backend:

```nginx
proxy_pass http://backend.demo.svc.cluster.local:8080/;
```

Luồng request:

```text
Browser
  -> Service frontend
  -> Pod frontend/Nginx
  -> Service backend
  -> Pod backend
```

## API Canary Với Argo Rollouts

Application cài controller:

```text
argocd/apps/argo-rollouts.yaml
```

Application triển khai API:

```text
argocd/apps/api.yaml
```

Manifest API:

```text
k8s-api/api.yaml
```

API dùng `kind: Rollout` thay vì `kind: Deployment`. Rollout là CRD của Argo Rollouts, hỗ trợ triển khai canary.

Chiến lược canary hiện tại:

```yaml
strategy:
  canary:
    steps:
      - setWeight: 25
      - pause: {}
      - setWeight: 50
      - pause:
          duration: 30s
      - setWeight: 100
```

Ý nghĩa:

- Đưa 25% traffic sang version mới.
- Pause để kiểm tra thủ công.
- Tăng lên 50%.
- Chờ 30 giây.
- Hoàn tất rollout 100%.

API expose qua Service:

```text
api.demo.svc.cluster.local:8080
```

Port Service có tên `http` để ServiceMonitor có thể scrape metrics theo tên port.

## Monitoring Với kube-prometheus-stack

Application:

```text
argocd/apps/kube-prometheus-stack.yaml
```

Chart Helm:

```yaml
repoURL: https://prometheus-community.github.io/helm-charts
chart: kube-prometheus-stack
targetRevision: 61.7.1
```

Stack này cài:

- Prometheus
- Grafana
- Alertmanager
- kube-state-metrics
- node-exporter
- Prometheus Operator
- Các CRD như `ServiceMonitor`, `PodMonitor`, `PrometheusRule`

File:

```text
k8s-api/servicemonitor.yaml
```

tạo `ServiceMonitor` để Prometheus scrape API:

```yaml
endpoints:
  - port: http
    path: /metrics
    interval: 15s
```

Nghĩa là Prometheus sẽ gọi endpoint `/metrics` của Service `api` mỗi 15 giây.

## Vì Sao kube-prometheus-stack Dùng Replace=true

`kube-prometheus-stack` tạo nhiều CRD lớn. Nếu apply theo kiểu mặc định, Kubernetes có thể lưu annotation `kubectl.kubernetes.io/last-applied-configuration` quá lớn và gây lỗi:

```text
metadata.annotations: Too long
```

Vì vậy Application monitoring dùng:

```yaml
syncOptions:
  - CreateNamespace=true
  - Replace=true
```

Ý nghĩa:

- `CreateNamespace=true`: Argo CD tự tạo namespace `monitoring`.
- `Replace=true`: dùng replace để tránh lỗi annotation quá dài khi sync CRD lớn.

## Automated Sync, Prune Và Self-Heal

Các Application đều bật:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Ý nghĩa:

- `automated`: Argo CD tự sync khi Git thay đổi.
- `prune`: nếu xóa resource khỏi Git, Argo CD xóa resource đó khỏi cluster.
- `selfHeal`: nếu ai sửa tay trong cluster, Argo CD đưa resource về lại đúng Git.

Ví dụ nếu scale frontend thủ công:

```bash
kubectl -n demo scale deploy/frontend --replicas=5
```

nhưng trong Git vẫn là:

```yaml
replicas: 1
```

Argo CD sẽ tự đưa frontend về lại `1` replica.

## Cách Apply Lần Đầu

Sau khi cluster đã có Argo CD, apply Application gốc:

```bash
kubectl apply -f argocd/root.yaml
```

Kiểm tra các Application:

```bash
kubectl -n argocd get applications
```

Kết quả mong đợi:

```text
NAME                    SYNC STATUS   HEALTH STATUS
api                     Synced        Healthy
argo-rollouts           Synced        Healthy
backend                 Synced        Healthy
demo-namespace          Synced        Healthy
frontend                Synced        Healthy
kube-prometheus-stack   Synced        Healthy
root                    Synced        Healthy
```

Kiểm tra workload trong namespace `demo`:

```bash
kubectl -n demo get all
```

Kiểm tra namespace monitoring:

```bash
kubectl -n monitoring get pods
```

## Cách Mở Frontend

Dùng port-forward:

```bash
kubectl -n demo port-forward svc/frontend 8080:80
```

Mở trình duyệt:

```text
http://localhost:8080
```

Trang frontend sẽ hiển thị:

```text
Frontend is running
hello from backend
```

Dòng `hello from backend` là kết quả frontend gọi backend qua route `/api/`.

## Cách Kiểm Tra Backend Trực Tiếp

Port-forward backend:

```bash
kubectl -n demo port-forward svc/backend 8081:8080
```

Mở:

```text
http://localhost:8081
```

Kết quả:

```text
hello from backend
```

## Cách Kiểm Tra API

Port-forward Service API:

```bash
kubectl -n demo port-forward svc/api 8082:8080
```

Gọi API:

```bash
curl http://localhost:8082/
```

Gọi metrics:

```bash
curl http://localhost:8082/metrics
```

Kiểm tra Rollout:

```bash
kubectl -n demo get rollout
kubectl -n demo describe rollout api
```

## Cách Mở Grafana

Port-forward Grafana:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

Mở:

```text
http://localhost:3000
```

Thông tin đăng nhập mặc định thường là:

```text
username: admin
password: prom-operator
```

Nếu password đã bị thay đổi bởi chart hoặc secret, xem bằng:

```bash
kubectl -n monitoring get secret kube-prometheus-stack-grafana -o jsonpath="{.data.admin-password}"
```

Sau đó decode base64 theo môi trường shell đang dùng.

## Validate Manifest

Có thể kiểm tra nhanh manifest bằng dry-run:

```bash
kubectl apply --dry-run=client --validate=false \
  -f argocd/root.yaml \
  -f argocd/apps \
  -f k8s/base \
  -f k8s/backend \
  -f k8s/frontend \
  -f k8s-api \
  -f k8s/web.yaml \
  -f k8s/namespace.yaml
```

Nếu dùng GitHub Actions, workflow validate có thể dùng `kubeconform` để bắt lỗi schema trước khi merge vào `main`.

## Rollback Theo GitOps

Không nên rollback lâu dài bằng lệnh thủ công như:

```bash
kubectl rollout undo
```

Lý do: nếu Git vẫn giữ version mới, Argo CD sẽ lại sync cluster về version trong Git.

Rollback đúng theo GitOps là revert commit:

```bash
git revert HEAD --no-edit
git push
```

Sau khi Git quay về trạng thái cũ, Argo CD sẽ sync cluster về trạng thái cũ.

## Tóm Tắt Luồng Hoạt Động

```text
1. Sửa YAML trong Git
2. Commit và push lên main
3. Argo CD root đọc argocd/apps
4. Root tạo hoặc cập nhật Application con
5. Application con apply manifest hoặc Helm chart
6. Kubernetes tạo Pod, Service, ConfigMap, CRD
7. Prometheus scrape metrics qua ServiceMonitor
8. Argo CD tiếp tục self-heal nếu cluster bị drift khỏi Git
```

## Tài Liệu Chi Tiết Hơn

Xem thêm:

```text
SYSTEM_FLOW.md
```

File này giải thích kỹ hơn cách các thành phần kết nối với nhau, vai trò từng thư mục và flow quan sát hệ thống.
