# GitOps với ArgoCD

Repo này dùng để demo luồng GitOps cơ bản: mọi trạng thái mong muốn của ứng dụng được khai báo trong Git, sau đó ArgoCD đọc Git và tự đồng bộ vào Kubernetes cluster.

Ý tưởng chính:

- Git là nơi lưu "mong muốn" của hệ thống.
- Kubernetes là nơi chạy thật.
- ArgoCD đứng giữa, so sánh Git với cluster rồi tự apply phần còn thiếu hoặc sửa phần bị lệch.

## Cấu trúc repo

```text
.
├── argocd
│   ├── root.yaml
│   └── apps
│       └── web.yaml
├── k8s
│   ├── namespace.yaml
│   └── web.yaml
└── .github
    └── workflows
        └── validate.yml
```

## Vì sao cần `argocd/root.yaml`

File `argocd/root.yaml` tạo một ArgoCD `Application` tên là `root`.

```yaml
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/pkhoa011004/github-action-argocd.git
    targetRevision: main
    path: argocd/apps
```

Mục đích của `root` là áp dụng mô hình **app-of-apps**.

Thay vì phải `kubectl apply` từng app một, ta chỉ apply `root` một lần. Sau đó `root` sẽ nhìn vào thư mục `argocd/apps` và tạo các application con nằm trong đó.

Hiện tại application con là:

- `argocd/apps/web.yaml`

Khi sau này có thêm app mới, chỉ cần thêm file mới vào `argocd/apps`, commit và push. ArgoCD sẽ tự thấy thay đổi đó.

### Vì sao cần `spec.project: default`

Trong ArgoCD, mọi `Application` phải thuộc một `AppProject`.

```yaml
spec:
  project: default
```

`default` là project mặc định được ArgoCD tạo sẵn. Nếu thiếu dòng này, ArgoCD sẽ báo lỗi:

```text
spec.project: Required value
```

## Vì sao cần `argocd/apps/web.yaml`

File này tạo ArgoCD `Application` tên là `web`.

```yaml
kind: Application
metadata:
  name: web
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/pkhoa011004/github-action-argocd.git
    targetRevision: main
    path: k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
```

Ý nghĩa:

- `repoURL`: ArgoCD lấy manifest từ repo GitHub này.
- `targetRevision: main`: ArgoCD theo dõi branch `main`.
- `path: k8s`: ArgoCD chỉ apply các file trong thư mục `k8s`.
- `destination.server`: apply vào Kubernetes cluster hiện tại.
- `destination.namespace: demo`: app web chạy trong namespace `demo`.

Phần sync policy:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Ý nghĩa:

- `automated`: có thay đổi trên Git thì ArgoCD tự sync, không cần bấm tay.
- `prune: true`: nếu xóa resource khỏi Git, ArgoCD cũng xóa resource đó trong cluster.
- `selfHeal: true`: nếu ai sửa tay trong cluster, ArgoCD kéo lại đúng như Git.

Ví dụ: trong Git đang là `replicas: 4`. Nếu ai chạy:

```bash
kubectl -n demo scale deploy/web --replicas=9
```

ArgoCD sẽ phát hiện cluster bị lệch khỏi Git và tự đưa về `4`.

## Vì sao cần `k8s/namespace.yaml`

File này tạo namespace `demo`.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: demo
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
```

Namespace là "không gian" để chứa các resource của app web.

Ta cần tạo namespace trước, vì các resource khác như `ConfigMap`, `Deployment`, `Service` đều khai báo:

```yaml
namespace: demo
```

Nếu namespace chưa tồn tại mà apply các resource kia trước, Kubernetes có thể báo lỗi namespace không tồn tại.

Annotation này:

```yaml
argocd.argoproj.io/sync-wave: "-1"
```

nói với ArgoCD rằng resource này phải chạy sớm hơn các resource wave `0`, `1`, `2`.

## Vì sao cần `k8s/web.yaml`

File `k8s/web.yaml` chứa 3 resource chính của app web:

- `ConfigMap`
- `Deployment`
- `Service`

Ba resource này cùng mô tả cách app được cấu hình, chạy và được truy cập trong cluster.

## `ConfigMap web-config` dùng để làm gì

```yaml
kind: ConfigMap
metadata:
  name: web-config
  namespace: demo
  annotations:
    argocd.argoproj.io/sync-wave: "0"
data:
  MESSAGE: "hello from gitops"
```

`ConfigMap` dùng để lưu cấu hình không nhạy cảm của ứng dụng.

Trong file hiện tại, ta có biến:

```yaml
MESSAGE: "hello from gitops"
```

Deployment đọc config này bằng:

```yaml
envFrom:
  - configMapRef:
      name: web-config
```

Vì Deployment cần đọc `web-config`, nên `ConfigMap` được gắn sync-wave `0`, chạy trước Deployment wave `1`.

## `Deployment web` dùng để làm gì

```yaml
kind: Deployment
metadata:
  name: web
  namespace: demo
spec:
  replicas: 4
```

`Deployment` mô tả cách chạy app.

Trong repo này, Deployment nói rằng:

- chạy image `nginx:1.27`
- mở port container `80`
- tạo `4` bản sao của app
- gắn label `app: web`
- đọc biến môi trường từ `ConfigMap web-config`

Phần quan trọng:

```yaml
replicas: 4
```

Nghĩa là Kubernetes phải luôn giữ 4 pod web chạy.

Nếu 1 pod chết, Kubernetes tạo pod mới. Nếu ai scale lên 9 pod bằng tay, ArgoCD self-heal sẽ đưa lại về 4 vì Git đang ghi là 4.

## Vì sao ArgoCD UI có `ReplicaSet` và `Pod`

Trong Git ta chỉ khai báo `Deployment`, không khai báo trực tiếp `ReplicaSet` hay `Pod`.

Nhưng trên ArgoCD UI lại thấy:

```text
Deployment web
└── ReplicaSet web-84cd54c848
    ├── Pod web-84cd54c848-2cdqd
    ├── Pod web-84cd54c848-l7bqg
    ├── Pod web-84cd54c848-mn5sm
    └── Pod web-84cd54c848-sqblx
```

Lý do là Kubernetes controller tự sinh ra các resource con:

- `Deployment` tạo và quản lý `ReplicaSet`.
- `ReplicaSet` tạo và giữ đúng số lượng `Pod`.
- `Pod` là nơi container thật sự chạy.

Ta không commit `ReplicaSet` và `Pod` vào Git vì chúng là resource phát sinh tự động.

## `Service web` dùng để làm gì

```yaml
kind: Service
metadata:
  name: web
  namespace: demo
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 80
```

`Service` tạo một địa chỉ ổn định để truy cập các pod.

Pod có thể bị xóa và tạo lại, tên pod cũng thay đổi. Nếu truy cập trực tiếp pod thì không ổn định. Service giải quyết việc đó bằng cách tìm các pod có label:

```yaml
app: web
```

rồi chuyển traffic vào port `80` của các pod đó.

## Vì sao ArgoCD UI có `Endpoint` và `EndpointSlice`

Trong ảnh ArgoCD, dưới `Service web` có:

- `ep web`
- `endpointslice web-kw2c9`

Đây là resource Kubernetes tự tạo để Service biết danh sách pod nào đang sẵn sàng nhận traffic.

Ta không viết `Endpoint` hoặc `EndpointSlice` trong Git. Kubernetes tự tạo dựa trên:

- selector của Service: `app: web`
- label của pod: `app: web`
- trạng thái pod: running, ready

## Vì sao cần sync-wave

Các resource trong repo có thứ tự sync:

```text
Namespace  -1
ConfigMap   0
Deployment  1
Service     2
```

Mục đích:

- Namespace chạy đầu tiên để các resource trong `demo` có nơi để tạo.
- ConfigMap chạy trước Deployment để container đọc được config.
- Deployment chạy sau ConfigMap để tạo pod.
- Service chạy sau cùng để trỏ vào các pod có label `app: web`.

Nếu thiếu thứ tự này, một số resource vẫn có thể tự retry, nhưng lab này cố tình dùng sync-wave để nhìn rõ cách ArgoCD điều phối thứ tự apply.

## Vì sao cần `.github/workflows/validate.yml`

File workflow này chạy trên Pull Request khi có thay đổi trong thư mục `k8s`.

```yaml
on:
  pull_request:
    paths:
      - "k8s/**"
```

Job chính:

```yaml
kubeconform -strict -summary k8s/
```

Mục đích là kiểm tra manifest Kubernetes trước khi merge vào `main`.

Luồng đúng:

1. Sửa manifest trong branch.
2. Tạo Pull Request.
3. GitHub Actions chạy validate.
4. Nếu manifest sai schema, PR bị báo đỏ.
5. Nếu manifest hợp lệ, PR có thể merge.
6. Sau khi merge vào `main`, ArgoCD sync thay đổi vào cluster.

Workflow này giúp tránh việc manifest lỗi đi thẳng vào cluster.

## Luồng hoạt động đầy đủ

1. Bạn commit các file YAML vào Git.
2. GitHub lưu trạng thái mong muốn.
3. ArgoCD `root` đọc thư mục `argocd/apps`.
4. `root` tạo application con `web`.
5. Application `web` đọc thư mục `k8s`.
6. ArgoCD apply `Namespace`, `ConfigMap`, `Deployment`, `Service`.
7. Kubernetes controller tự tạo `ReplicaSet`, `Pod`, `Endpoint`, `EndpointSlice`.
8. ArgoCD UI hiển thị toàn bộ cây resource như trong ảnh.

## Vì sao ảnh ArgoCD hiển thị như vậy

Trong ảnh, cây resource có dạng:

```text
Application web
├── ConfigMap web-config
├── Namespace demo
├── Service web
│   ├── Endpoint web
│   └── EndpointSlice web-kw2c9
└── Deployment web
    └── ReplicaSet web-84cd54c848
        ├── Pod web-84cd54c848-2cdqd
        ├── Pod web-84cd54c848-l7bqg
        ├── Pod web-84cd54c848-mn5sm
        └── Pod web-84cd54c848-sqblx
```

Điều này cho thấy:

- ArgoCD đã đọc được Git.
- Resource trong Git đã được apply vào cluster.
- Deployment đã tạo đủ 4 pod.
- Service đã tìm được các pod backend.
- App đang `Synced` và `Healthy`.

## Các lệnh kiểm tra hữu ích

Xem ArgoCD applications:

```bash
kubectl -n argocd get applications
```

Xem resource trong namespace `demo`:

```bash
kubectl -n demo get all
kubectl -n demo get configmap
```

Xem pod:

```bash
kubectl -n demo get pods
```

Test self-heal:

```bash
kubectl -n demo scale deploy/web --replicas=9
kubectl -n demo get deploy web -w
```

Sau vài giây, ArgoCD sẽ kéo số replica về lại giá trị trong Git.

Rollback đúng kiểu GitOps:

```bash
git revert HEAD --no-edit
git push
```

Không nên rollback bằng:

```bash
kubectl rollout undo
```

Vì nếu Git vẫn đang giữ version mới, ArgoCD sẽ lại sync cluster về version trong Git.

## Kết luận

Repo này minh họa đúng tinh thần GitOps:

- Muốn thay đổi app thì sửa Git.
- Muốn tăng hoặc giảm pod thì sửa `replicas` trong Git.
- Muốn rollback thì revert commit.
- Cluster luôn được ArgoCD kéo về trạng thái đã khai báo trong Git.

Nói ngắn gọn: **Git là nguồn sự thật, ArgoCD là người đồng bộ, Kubernetes là nơi chạy ứng dụng.**
