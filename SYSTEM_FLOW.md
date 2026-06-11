# Giải thích luồng hoạt động FE/BE với ArgoCD

Tài liệu này giải thích hệ thống trong repo, lý do có từng file YAML, và cách các thành phần kết nối với nhau.

## 1. Mục tiêu của hệ thống

Repo này dùng để demo GitOps với ArgoCD cho một ứng dụng có:

- `frontend`: trang web đơn giản chạy bằng Nginx.
- `backend`: API đơn giản trả về chuỗi `hello from backend`.
- `root`: ArgoCD Application gốc quản lý các Application con.

Ý tưởng chính:

```text
Git -> ArgoCD -> Kubernetes
```

Trong Git có các file YAML mô tả trạng thái mong muốn. ArgoCD đọc Git, so sánh với cluster, rồi tự động tạo, sửa hoặc xóa resource để cluster giống Git.

## 2. Luồng tổng quát

Hệ thống hiện tại chạy theo mô hình app-of-apps:

```text
argocd/root.yaml
  -> argocd/apps/namespace.yaml
  -> argocd/apps/backend.yaml
  -> argocd/apps/frontend.yaml
```

Nghĩa là:

1. Bạn apply `argocd/root.yaml` vào cluster.
2. ArgoCD tạo Application `root`.
3. `root` đọc thư mục `argocd/apps`.
4. Trong `argocd/apps`, root thấy 3 Application con:
   - `demo-namespace`
   - `backend`
   - `frontend`
5. Mỗi Application con lại đọc một thư mục riêng trong `k8s`.
6. Các manifest trong `k8s` tạo resource thật trên Kubernetes như Namespace, Deployment, Service, ConfigMap, Pod.

Hình dung cây quan hệ:

```text
root Application
├── demo-namespace Application
│   └── Namespace demo
├── backend Application
│   ├── Deployment backend
│   │   └── ReplicaSet
│   │       └── Pod backend
│   └── Service backend
└── frontend Application
    ├── ConfigMap frontend-html
    ├── ConfigMap frontend-nginx
    ├── Deployment frontend
    │   └── ReplicaSet
    │       └── Pod frontend
    └── Service frontend
```

## 3. Vì sao trong root không thấy Pod

Trong màn hình ArgoCD, khi mở app `root`, bạn chỉ thấy:

```text
root
├── backend
├── demo-namespace
└── frontend
```

Đây là đúng.

Lý do: `root` không tạo Pod trực tiếp. `root` chỉ tạo các ArgoCD Application con. Pod nằm bên trong app con `backend` và `frontend`.

Muốn xem Pod thì bấm vào app `backend` hoặc `frontend`. Ở đó ArgoCD sẽ hiện Deployment, ReplicaSet, Pod và Service.

Nói ngắn gọn:

```text
root quản lý Application
backend/frontend quản lý Deployment, Service, Pod
```

## 4. Cấu trúc thư mục

```text
.
├── argocd
│   ├── root.yaml
│   └── apps
│       ├── namespace.yaml
│       ├── backend.yaml
│       └── frontend.yaml
├── k8s
│   ├── base
│   │   └── namespace.yaml
│   ├── backend
│   │   └── backend.yaml
│   └── frontend
│       └── frontend.yaml
└── .github
    └── workflows
        └── validate.yml
```

## 5. Giải thích `argocd/root.yaml`

File:

```text
argocd/root.yaml
```

Mục đích: tạo Application gốc tên `root`.

Phần quan trọng:

```yaml
apiVersion: argoproj.io/v1alpha1
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

Giải thích:

- `kind: Application`: đây là resource của ArgoCD, không phải resource Kubernetes gốc.
- `metadata.name: root`: tên app hiển thị trên UI ArgoCD.
- `metadata.namespace: argocd`: Application được tạo trong namespace `argocd`.
- `project: default`: app thuộc ArgoCD project mặc định.
- `repoURL`: repo GitHub ArgoCD sẽ đọc.
- `targetRevision: main`: ArgoCD theo dõi branch `main`.
- `path: argocd/apps`: root đọc các file Application con trong thư mục này.

Phần này:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

có nghĩa:

- `automated`: có thay đổi trên Git thì ArgoCD tự sync.
- `prune`: xóa file/resource khỏi Git thì ArgoCD xóa resource tương ứng trong cluster.
- `selfHeal`: nếu ai sửa tay trong cluster, ArgoCD đưa lại về đúng Git.

## 6. Giải thích `argocd/apps/namespace.yaml`

File:

```text
argocd/apps/namespace.yaml
```

Mục đích: tạo Application con `demo-namespace`.

Application này trỏ vào:

```yaml
path: k8s/base
```

Nghĩa là nó sẽ apply file:

```text
k8s/base/namespace.yaml
```

Annotation:

```yaml
argocd.argoproj.io/sync-wave: "-1"
```

nói với ArgoCD rằng app này nên được sync trước backend và frontend.

Lý do: namespace `demo` phải có trước thì backend/frontend mới tạo resource vào namespace `demo` được.

## 7. Giải thích `k8s/base/namespace.yaml`

File:

```text
k8s/base/namespace.yaml
```

Nội dung:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: demo
```

Mục đích: tạo namespace `demo`.

Namespace giống như một khu vực riêng trong Kubernetes. Các resource của FE và BE đều nằm trong namespace này.

Nếu không có namespace `demo`, các Deployment/Service có:

```yaml
namespace: demo
```

sẽ không tạo được.

## 8. Giải thích `argocd/apps/backend.yaml`

File:

```text
argocd/apps/backend.yaml
```

Mục đích: tạo Application con `backend`.

Phần quan trọng:

```yaml
source:
  repoURL: https://github.com/pkhoa011004/github-action-argocd.git
  targetRevision: main
  path: k8s/backend
destination:
  server: https://kubernetes.default.svc
  namespace: demo
```

Giải thích:

- `path: k8s/backend`: backend app đọc manifest trong thư mục `k8s/backend`.
- `destination.namespace: demo`: resource backend được tạo trong namespace `demo`.
- `sync-wave: "0"`: backend sync sau namespace và trước frontend.

Backend cần chạy trước frontend vì frontend sẽ gọi backend qua service DNS nội bộ.

## 9. Giải thích `k8s/backend/backend.yaml`

File này chứa 2 resource:

- `Deployment backend`
- `Service backend`

### 9.1 Deployment backend

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: demo
spec:
  replicas: 1
```

Mục đích: tạo backend container.

Phần container:

```yaml
containers:
  - name: backend
    image: hashicorp/http-echo:1.0
    args:
      - "-listen=:8080"
      - "-text=hello from backend"
    ports:
      - containerPort: 8080
```

Giải thích:

- Image `hashicorp/http-echo:1.0` là một HTTP server rất nhỏ.
- Nó lắng nghe port `8080`.
- Khi có request, nó trả về text `hello from backend`.

Phần selector/label:

```yaml
selector:
  matchLabels:
    app: backend
template:
  metadata:
    labels:
      app: backend
```

Deployment dùng label `app: backend` để quản lý Pod của nó.

Kubernetes tự động tạo:

```text
Deployment backend -> ReplicaSet -> Pod backend
```

Ta không viết ReplicaSet và Pod trong Git vì Kubernetes tự sinh ra chúng.

### 9.2 Readiness và liveness probe

```yaml
readinessProbe:
  httpGet:
    path: /
    port: 8080
livenessProbe:
  httpGet:
    path: /
    port: 8080
```

Ý nghĩa:

- `readinessProbe`: kiểm tra pod đã sẵn sàng nhận traffic chưa.
- `livenessProbe`: kiểm tra pod còn sống không.

Nếu liveness fail, Kubernetes có thể restart container.

### 9.3 Service backend

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: demo
spec:
  selector:
    app: backend
  ports:
    - port: 8080
      targetPort: 8080
```

Mục đích: tạo địa chỉ ổn định để frontend gọi backend.

Service tìm các Pod có label:

```yaml
app: backend
```

rồi chuyển request vào `targetPort: 8080`.

DNS nội bộ của service backend là:

```text
backend.demo.svc.cluster.local:8080
```

Frontend sẽ gọi backend qua địa chỉ này.

## 10. Giải thích `argocd/apps/frontend.yaml`

File:

```text
argocd/apps/frontend.yaml
```

Mục đích: tạo Application con `frontend`.

Phần quan trọng:

```yaml
source:
  path: k8s/frontend
destination:
  namespace: demo
```

Nghĩa là frontend app đọc manifest trong:

```text
k8s/frontend
```

và tạo resource trong namespace:

```text
demo
```

Annotation:

```yaml
argocd.argoproj.io/sync-wave: "1"
```

Nghĩa là frontend sync sau backend.

## 11. Giải thích `k8s/frontend/frontend.yaml`

File này chứa 4 resource:

- `ConfigMap frontend-html`
- `ConfigMap frontend-nginx`
- `Deployment frontend`
- `Service frontend`

### 11.1 ConfigMap `frontend-html`

```yaml
kind: ConfigMap
metadata:
  name: frontend-html
data:
  index.html: |
    ...
```

Mục đích: lưu nội dung file HTML của frontend.

Trong HTML có đoạn JavaScript:

```javascript
fetch("/api/")
  .then((response) => response.text())
```

Nghĩa là khi browser mở trang frontend, frontend sẽ gọi endpoint `/api/`.

### 11.2 ConfigMap `frontend-nginx`

```yaml
kind: ConfigMap
metadata:
  name: frontend-nginx
data:
  default.conf: |
    server {
      listen 80;

      location / {
        root /usr/share/nginx/html;
        index index.html;
      }

      location /api/ {
        proxy_pass http://backend.demo.svc.cluster.local:8080/;
      }
    }
```

Mục đích: cấu hình Nginx.

Có 2 route quan trọng:

- `/`: trả về file `index.html`.
- `/api/`: proxy request sang backend.

Backend được gọi qua DNS nội bộ:

```text
backend.demo.svc.cluster.local:8080
```

Do đó browser không cần biết service backend nằm ở đâu. Browser chỉ gọi frontend, frontend proxy tiếp sang backend.

### 11.3 Deployment frontend

```yaml
kind: Deployment
metadata:
  name: frontend
  namespace: demo
spec:
  replicas: 1
```

Mục đích: chạy Nginx frontend.

Container:

```yaml
containers:
  - name: frontend
    image: nginx:1.27
    ports:
      - containerPort: 80
```

Frontend chạy Nginx và mở port 80.

Phần mount ConfigMap:

```yaml
volumeMounts:
  - name: frontend-html
    mountPath: /usr/share/nginx/html/index.html
    subPath: index.html
  - name: frontend-nginx
    mountPath: /etc/nginx/conf.d/default.conf
    subPath: default.conf
```

Ý nghĩa:

- Mount `index.html` từ ConfigMap vào thư mục web của Nginx.
- Mount `default.conf` từ ConfigMap vào cấu hình Nginx.

Nhờ vậy ta không cần build image frontend riêng. Chỉ cần dùng image `nginx:1.27` và nạp HTML/config bằng ConfigMap.

### 11.4 Service frontend

```yaml
kind: Service
metadata:
  name: frontend
  namespace: demo
spec:
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: 80
```

Mục đích: tạo địa chỉ ổn định cho frontend.

Service frontend tìm các Pod có label:

```yaml
app: frontend
```

rồi chuyển traffic vào port 80 của Pod.

Khi muốn mở app trên máy local, dùng:

```bash
kubectl -n demo port-forward svc/frontend 8080:80
```

Sau đó mở:

```text
http://localhost:8080
```

## 12. Luồng request từ người dùng đến backend

Khi người dùng mở frontend:

```text
Browser -> Service frontend -> Pod frontend/Nginx -> index.html
```

Sau khi trang load, JavaScript gọi:

```text
GET /api/
```

Nginx trong frontend nhận request `/api/` và proxy sang backend:

```text
Browser -> Service frontend -> Pod frontend/Nginx -> Service backend -> Pod backend
```

Backend trả về:

```text
hello from backend
```

Frontend hiển thị kết quả đó trên trang web.

## 13. Sync-wave hoạt động như thế nào

Sync-wave dùng để ép thứ tự apply.

Ở cấp Application:

```text
demo-namespace  wave -1
backend         wave  0
frontend        wave  1
```

Ở cấp resource Kubernetes:

```text
Namespace               wave -1
Backend Deployment      wave  0
Backend Service         wave  1
Frontend ConfigMaps     wave  0
Frontend Deployment     wave  1
Frontend Service        wave  2
```

Mục đích:

- Namespace có trước.
- Backend có trước frontend.
- ConfigMap có trước Deployment.
- Service tạo sau khi selector/label đã sẵn sàng.

## 14. Giải thích `.github/workflows/validate.yml`

File:

```text
.github/workflows/validate.yml
```

Mục đích: kiểm tra manifest Kubernetes khi tạo Pull Request.

Workflow chạy khi có thay đổi trong:

```yaml
paths:
  - "k8s/**"
```

Nghĩa là nếu sửa file trong thư mục `k8s`, GitHub Actions sẽ chạy job `validate`.

Job cài `kubeconform`:

```bash
curl -sSLo kc.tgz https://github.com/yannh/kubeconform/releases/download/v0.6.7/kubeconform-linux-amd64.tar.gz
tar -xzf kc.tgz
sudo mv kubeconform /usr/local/bin/
```

Sau đó validate:

```bash
kubeconform -strict -summary k8s/
```

Mục đích là bắt lỗi YAML/schema trước khi merge vào `main`.

Ví dụ nếu khai báo sai:

```yaml
replicas: five
```

thì validate sẽ fail, vì `replicas` phải là số:

```yaml
replicas: 5
```

## 15. Các lệnh kiểm tra

Apply root lần đầu:

```bash
kubectl apply -f argocd/root.yaml
```

Xem các ArgoCD Application:

```bash
kubectl -n argocd get applications
```

Xem resource trong namespace `demo`:

```bash
kubectl -n demo get all
```

Xem pod:

```bash
kubectl -n demo get pods
```

Mở frontend:

```bash
kubectl -n demo port-forward svc/frontend 8080:80
```

Mở trình duyệt:

```text
http://localhost:8080
```

Kiểm tra backend trực tiếp trong cluster:

```bash
kubectl -n demo port-forward svc/backend 8081:8080
```

Sau đó mở:

```text
http://localhost:8081
```

## 16. Test self-heal

Nếu sửa tay frontend trong cluster:

```bash
kubectl -n demo scale deploy/frontend --replicas=5
```

nhưng trong Git vẫn là:

```yaml
replicas: 1
```

thì ArgoCD sẽ đưa frontend về lại 1 replica.

Đây là self-heal.

## 17. Rollback đúng cách GitOps

Không nên rollback bằng:

```bash
kubectl rollout undo
```

Lý do: nếu Git vẫn giữ version mới, ArgoCD sẽ lại sync cluster về version trong Git.

Rollback đúng cách GitOps là revert commit:

```bash
git revert HEAD --no-edit
git push
```

Sau khi Git đổi về trạng thái cũ, ArgoCD sẽ sync cluster về trạng thái cũ.

## 18. Tóm tắt từng file YAML

| File | Vai trò |
| --- | --- |
| `argocd/root.yaml` | Application gốc, đọc `argocd/apps` |
| `argocd/apps/namespace.yaml` | Application con tạo namespace |
| `argocd/apps/backend.yaml` | Application con quản lý backend |
| `argocd/apps/frontend.yaml` | Application con quản lý frontend |
| `k8s/base/namespace.yaml` | Tạo namespace `demo` |
| `k8s/backend/backend.yaml` | Tạo Deployment và Service backend |
| `k8s/frontend/frontend.yaml` | Tạo HTML, Nginx config, Deployment và Service frontend |
| `.github/workflows/validate.yml` | Validate manifest khi có Pull Request |

## 19. Kết luận

Hệ thống này tách rõ 2 lớp:

```text
Lớp ArgoCD Application:
root -> namespace/backend/frontend

Lớp Kubernetes resource:
namespace/backend/frontend -> Deployment/Service/ConfigMap/Pod
```

Vì vậy khi nhìn UI:

- Mở `root` thì thấy các Application con.
- Mở `backend` thì thấy Deployment, Service, Pod backend.
- Mở `frontend` thì thấy ConfigMap, Deployment, Service, Pod frontend.

Đây là hành vi đúng của mô hình app-of-apps trong ArgoCD.
