# Giải Thích Các File YAML Trong Dự Án

Tài liệu này giải thích các file `.yaml` dùng để làm gì trong hệ thống GitOps Kubernetes.

Luồng tổng thể:

```text
argocd/root.yaml
  -> argocd/apps/*.yaml
  -> k8s/base, k8s/backend, k8s/frontend, k8s-api
  -> Kubernetes tạo namespace, pod, service, rollout, monitoring
```

## 1. Nhóm Argo CD YAML

Các file trong `argocd/` không tạo pod ứng dụng trực tiếp. Chúng tạo `Application` của Argo CD. Argo CD dùng các Application này để đọc manifest hoặc Helm chart rồi sync vào Kubernetes.

### `argocd/root.yaml`

Vai trò:

- Tạo Argo CD Application cha tên `root`.
- Dùng mô hình App-of-Apps.
- `root` đọc thư mục `argocd/apps`.
- Từ đó tạo các Application con như backend, frontend, api, argo-rollouts, kube-prometheus-stack.

Luồng:

```text
kubectl apply -f argocd/root.yaml
  -> Argo CD tạo root app
  -> root app đọc argocd/apps
  -> tạo các app con
```

Vì sao cần:

- Chỉ cần apply một file root ban đầu.
- Sau đó Argo CD tự quản lý toàn bộ hệ thống từ Git.

### `argocd/apps/namespace.yaml`

Vai trò:

- Tạo Argo CD Application tên `demo-namespace`.
- App này sync manifest trong `k8s/base`.
- Mục tiêu là tạo namespace `demo`.

Nó không tự tạo namespace trực tiếp trong file này. Nó nói với Argo CD rằng hãy đọc `k8s/base`.

### `argocd/apps/backend.yaml`

Vai trò:

- Tạo Argo CD Application tên `backend`.
- App này sync thư mục `k8s/backend`.
- Dùng để deploy backend Deployment và backend Service vào namespace `demo`.

Luồng:

```text
argocd/apps/backend.yaml
  -> Argo CD đọc k8s/backend
  -> tạo Deployment backend
  -> tạo Service backend
```

### `argocd/apps/frontend.yaml`

Vai trò:

- Tạo Argo CD Application tên `frontend`.
- App này sync thư mục `k8s/frontend`.
- Dùng để deploy frontend Nginx, ConfigMap HTML, ConfigMap Nginx và Service frontend.

Luồng:

```text
argocd/apps/frontend.yaml
  -> Argo CD đọc k8s/frontend
  -> tạo ConfigMap
  -> tạo Deployment frontend
  -> tạo Service frontend
```

### `argocd/apps/api.yaml`

Vai trò:

- Tạo Argo CD Application tên `api`.
- App này sync thư mục `k8s-api`.
- Dùng để deploy API bằng Argo Rollouts.

Trong `k8s-api` có:

- `api.yaml`
- `servicemonitor.yaml`
- `prometheus-rules.yaml`

Luồng:

```text
argocd/apps/api.yaml
  -> Argo CD đọc k8s-api
  -> tạo Rollout api
  -> tạo Service api
  -> tạo ServiceMonitor api
  -> tạo PrometheusRule api-rules
```

Vì sao app `api` sync sau các app khác:

- API cần namespace `demo`.
- API cần CRD `Rollout` từ Argo Rollouts.
- API cần CRD `ServiceMonitor` và `PrometheusRule` từ kube-prometheus-stack.

### `argocd/apps/argo-rollouts.yaml`

Vai trò:

- Tạo Argo CD Application tên `argo-rollouts`.
- App này cài Argo Rollouts bằng Helm chart.
- Tạo namespace `argo-rollouts`.
- Cài controller và CRD `Rollout`.

Vì sao cần:

- Kubernetes mặc định không hiểu `kind: Rollout`.
- Argo Rollouts controller cần được cài trước để xử lý API Rollout.

### `argocd/apps/kube-prometheus-stack.yaml`

Vai trò:

- Tạo Argo CD Application tên `kube-prometheus-stack`.
- Cài monitoring stack bằng Helm chart `kube-prometheus-stack`.
- Tạo namespace `monitoring`.

Chart này cài:

- Prometheus
- Alertmanager
- Grafana
- kube-state-metrics
- node-exporter
- Prometheus Operator
- CRD `ServiceMonitor`
- CRD `PrometheusRule`

File này cũng cấu hình Alertmanager gửi mail qua Gmail.

Luồng alert:

```text
PrometheusRule
  -> Prometheus
  -> Alertmanager
  -> Gmail
```

## 2. Nhóm Kubernetes Base

### `k8s/base/namespace.yaml`

Vai trò:

- Tạo namespace `demo`.
- Đây là namespace chính để chạy frontend, backend và API.

Vì sao cần:

- Các workload như backend, frontend, API đều khai báo `namespace: demo`.
- Namespace phải tồn tại trước khi tạo workload.

### `k8s/namespace.yaml`

Vai trò:

- Cũng tạo namespace `demo`.
- Đây là manifest demo độc lập, không phải luồng chính của Argo CD App-of-Apps hiện tại.

Lưu ý:

- Luồng chính dùng `k8s/base/namespace.yaml`.
- `k8s/namespace.yaml` có thể dùng cho lab hoặc test thủ công.

## 3. Nhóm Backend

### `k8s/backend/backend.yaml`

Vai trò:

- Tạo Deployment backend.
- Tạo Service backend.

Deployment backend:

- Chạy image `hashicorp/http-echo`.
- Trả response demo.
- Có readiness/liveness probe.

Service backend:

- Tạo endpoint ổn định cho backend.
- Frontend hoặc service khác có thể gọi backend qua service DNS.

Luồng:

```text
Service backend
  -> chọn pod label app=backend
  -> forward traffic vào container backend
```

## 4. Nhóm Frontend

### `k8s/frontend/frontend.yaml`

Vai trò:

- Tạo ConfigMap chứa HTML frontend.
- Tạo ConfigMap chứa cấu hình Nginx.
- Tạo Deployment frontend.
- Tạo Service frontend.

Frontend chạy bằng Nginx.

Luồng:

```text
Browser
  -> Service frontend
  -> Pod frontend Nginx
  -> HTML
```

Nếu frontend proxy API/backend:

```text
Browser gọi /api
  -> frontend Nginx
  -> backend hoặc api Service
```

## 5. Nhóm API

### `k8s-api/api.yaml`

Vai trò:

- Tạo `Rollout` API.
- Tạo Service API.
- Tạo `AnalysisTemplate` kiểm tra error rate bằng Prometheus.

Resource chính trong file này:

| Resource | Vai trò |
| --- | --- |
| `Rollout api` | Chạy API Flask bằng Argo Rollouts |
| `Service api` | Expose API trong namespace `demo` |
| `AnalysisTemplate api-error-rate` | Query Prometheus để kiểm tra error rate khi canary |

Rollout API:

- Chạy image `w9-api:1`.
- Có nhiều replica.
- Có readinessProbe `/healthz`.
- Có resource requests/limits.
- Có canary steps.

Service API:

- Chọn pod có label `app=api`.
- Expose port `8080`.
- Đặt port name `http` để ServiceMonitor scrape được.

AnalysisTemplate:

- Query Prometheus.
- Kiểm tra tỉ lệ lỗi 5xx.
- Nếu error rate vượt ngưỡng, rollout có thể fail.

Luồng canary:

```text
Argo CD sync Rollout api
  -> Argo Rollouts tạo pod API
  -> setWeight 25%
  -> chạy analysis
  -> pause
  -> setWeight 50%
  -> chạy analysis
  -> hoàn tất rollout
```

### `k8s-api/servicemonitor.yaml`

Vai trò:

- Tạo `ServiceMonitor` cho API.
- Báo cho Prometheus biết cần scrape Service `api`.

Thông tin chính:

- Namespace: `demo`
- Selector: Service có label `app=api`
- Port: `http`
- Path: `/metrics`
- Interval: `15s`

Luồng:

```text
Prometheus
  -> đọc ServiceMonitor api
  -> tìm Service app=api
  -> scrape /metrics trên port http
```

Vì sao cần:

- Nếu không có ServiceMonitor, Prometheus không biết phải scrape API.
- Alert error rate/latency cần metrics từ API.

### `k8s-api/prometheus-rules.yaml`

Vai trò:

- Tạo `PrometheusRule` tên `api-rules`.
- Định nghĩa các alert rule cho API và hệ thống.

Các alert chính:

| Alert | Mục đích |
| --- | --- |
| `HighCPUUsage` | Cảnh báo CPU cao |
| `HighMemoryUsage` | Cảnh báo memory cao |
| `PodCrashLooping` | Cảnh báo pod crash/restart |
| `ApiServiceDown` | Cảnh báo API down |
| `ApiHighErrorRate` | Cảnh báo 5xx error rate cao |
| `ApiHighLatency` | Cảnh báo latency cao |
| `ApiSLOBurnRateHigh` | Cảnh báo SLO burn rate |
| `ApiCanaryHighErrorRate` | Cảnh báo canary lỗi |
| `NodeDiskAlmostFull` | Cảnh báo disk gần đầy |

Luồng alert:

```text
Prometheus scrape metrics
  -> PrometheusRule đánh giá PromQL
  -> Alert firing
  -> Alertmanager nhận alert
  -> Gmail
```

## 6. Nhóm Demo Độc Lập

### `k8s/web.yaml`

Vai trò:

- Tạo một web demo độc lập.
- Gồm ConfigMap, Deployment và Service.
- Không phải luồng chính của App-of-Apps hiện tại.

Lưu ý:

- File này hữu ích để test Kubernetes cơ bản.
- Nhưng flow chính của dự án là frontend/backend/API trong các thư mục riêng.

### `k8s/api/prometheus-rules.yaml`

Vai trò:

- Là bản PrometheusRule trong thư mục `k8s/api`.
- Nội dung dùng để tham khảo hoặc đồng bộ với `k8s-api/prometheus-rules.yaml`.

Lưu ý quan trọng:

- Argo CD Application `api` hiện sync thư mục `k8s-api`.
- Vì vậy rule chính được deploy là `k8s-api/prometheus-rules.yaml`.

## 7. Thứ Tự Chạy Của Các YAML

Thứ tự logic:

```text
1. argocd/root.yaml
2. argocd/apps/namespace.yaml
3. k8s/base/namespace.yaml
4. argocd/apps/backend.yaml -> k8s/backend/backend.yaml
5. argocd/apps/frontend.yaml -> k8s/frontend/frontend.yaml
6. argocd/apps/argo-rollouts.yaml
7. argocd/apps/kube-prometheus-stack.yaml
8. argocd/apps/api.yaml -> k8s-api/*
```

Giải thích:

- Namespace phải có trước workload.
- Argo Rollouts phải có trước `kind: Rollout`.
- kube-prometheus-stack phải có trước `ServiceMonitor` và `PrometheusRule`.
- API deploy sau cùng vì API cần cả Rollouts và monitoring CRD.

## 8. Tóm Tắt Nhanh

| File | Dùng để làm gì |
| --- | --- |
| `argocd/root.yaml` | App cha App-of-Apps |
| `argocd/apps/*.yaml` | Các Argo CD Application con |
| `k8s/base/namespace.yaml` | Tạo namespace `demo` |
| `k8s/backend/backend.yaml` | Deploy backend |
| `k8s/frontend/frontend.yaml` | Deploy frontend |
| `k8s-api/api.yaml` | Deploy API bằng Argo Rollouts |
| `k8s-api/servicemonitor.yaml` | Cho Prometheus scrape API |
| `k8s-api/prometheus-rules.yaml` | Tạo alert rule |
| `k8s/web.yaml` | Web demo độc lập |
| `k8s/namespace.yaml` | Namespace demo độc lập |

## 9. Câu Trả Lời Ngắn Với Mentor

Nếu mentor hỏi "các file YAML dùng để làm gì?", có thể trả lời:

```text
Nhóm argocd/*.yaml dùng để khai báo Argo CD Application.
root.yaml là app cha, còn argocd/apps/*.yaml là các app con.
Các app con trỏ đến thư mục k8s hoặc k8s-api để deploy resource thật.
k8s/base tạo namespace demo.
k8s/backend và k8s/frontend deploy backend/frontend.
k8s-api/api.yaml deploy API bằng Argo Rollouts.
k8s-api/servicemonitor.yaml cho Prometheus scrape API.
k8s-api/prometheus-rules.yaml tạo alert rule để Alertmanager gửi Gmail.
```
