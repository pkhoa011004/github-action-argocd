# GitOps FE/BE voi ArgoCD

Repo nay demo mot he thong GitOps don gian gom:

- `root`: ArgoCD Application goc, dung mo hinh app-of-apps.
- `demo-namespace`: tao namespace `demo`.
- `backend`: mot API don gian tra ve text `hello from backend`.
- `frontend`: mot Nginx frontend serve HTML va proxy `/api/` sang backend.

Trong GitOps, Git la nguon su that. Muon thay doi app thi sua YAML trong Git, commit, push. ArgoCD se doc Git va dong bo cluster ve dung trang thai trong Git.

## Cau truc repo

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

File `k8s/web.yaml` va `k8s/namespace.yaml` cu van con trong repo de tham khao lab truoc, nhung `root` hien tai khong sync app `web` nua.

## Root Application

File:

```text
argocd/root.yaml
```

Noi dung quan trong:

```yaml
source:
  repoURL: https://github.com/pkhoa011004/github-action-argocd.git
  targetRevision: main
  path: argocd/apps
```

`root` khong tro truc tiep vao FE hay BE. `root` tro vao thu muc `argocd/apps`. Moi file Application trong thu muc do se duoc root tao ra.

Hien tai root se tao 3 app con:

- `demo-namespace`
- `backend`
- `frontend`

Day la mo hinh **app-of-apps**.

## Vi sao can `project: default`

Moi ArgoCD Application phai thuoc mot AppProject.

```yaml
spec:
  project: default
```

Neu thieu dong nay, ArgoCD bao loi:

```text
spec.project: Required value
```

`default` la project mac dinh duoc ArgoCD tao san.

## App `demo-namespace`

File:

```text
argocd/apps/namespace.yaml
```

App nay doc manifest tu:

```yaml
path: k8s/base
```

File Kubernetes that:

```text
k8s/base/namespace.yaml
```

Muc dich la tao namespace `demo` truoc khi tao backend va frontend.

Annotation sync-wave:

```yaml
argocd.argoproj.io/sync-wave: "-1"
```

nghia la app namespace chay truoc cac app wave `0` va `1`.

## App `backend`

File ArgoCD:

```text
argocd/apps/backend.yaml
```

No tro vao:

```yaml
path: k8s/backend
destination:
  namespace: demo
```

File Kubernetes:

```text
k8s/backend/backend.yaml
```

Backend gom:

- `Deployment backend`
- `Service backend`

Deployment chay image:

```yaml
image: hashicorp/http-echo:1.0
```

Container lang nghe port `8080` va tra ve:

```text
hello from backend
```

Service `backend` tao DNS noi bo trong cluster:

```text
backend.demo.svc.cluster.local:8080
```

Frontend se goi backend thong qua dia chi nay.

## App `frontend`

File ArgoCD:

```text
argocd/apps/frontend.yaml
```

No tro vao:

```yaml
path: k8s/frontend
destination:
  namespace: demo
```

File Kubernetes:

```text
k8s/frontend/frontend.yaml
```

Frontend gom:

- `ConfigMap frontend-html`: chua file `index.html`.
- `ConfigMap frontend-nginx`: chua cau hinh Nginx.
- `Deployment frontend`: chay Nginx.
- `Service frontend`: tao service cho frontend.

Nginx serve HTML o duong dan `/`.

Khi browser goi:

```text
/api/
```

Nginx proxy request sang backend:

```nginx
proxy_pass http://backend.demo.svc.cluster.local:8080/;
```

Nghia la nguoi dung chi can mo frontend. Frontend se tu goi backend noi bo trong cluster.

## Thu tu sync

Root tao cac app con theo thu tu:

```text
demo-namespace  wave -1
backend         wave  0
frontend        wave  1
```

Trong tung app, resource Kubernetes cung co sync-wave rieng.

Backend:

```text
Deployment backend  wave 0
Service backend     wave 1
```

Frontend:

```text
ConfigMap frontend-html   wave 0
ConfigMap frontend-nginx  wave 0
Deployment frontend       wave 1
Service frontend          wave 2
```

Thu tu nay giup:

- Namespace co truoc.
- Backend co truoc frontend.
- ConfigMap co truoc Deployment.
- Service duoc tao sau khi selector da ro rang.

## Tu sync, prune va self-heal

Tat ca Application deu co:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Y nghia:

- `automated`: push len Git thi ArgoCD tu sync.
- `prune`: xoa resource khoi Git thi ArgoCD xoa khoi cluster.
- `selfHeal`: ai sua tay trong cluster thi ArgoCD sua lai theo Git.

Vi du neu ai scale frontend bang tay:

```bash
kubectl -n demo scale deploy/frontend --replicas=5
```

nhung trong Git la:

```yaml
replicas: 1
```

thi ArgoCD se keo frontend ve lai 1 replica.

## Cach apply lan dau

Sau khi cai ArgoCD vao cluster, chi can apply root:

```bash
kubectl apply -f argocd/root.yaml
```

Sau do kiem tra:

```bash
kubectl -n argocd get applications
kubectl -n demo get all
```

Ban se thay cac app:

```text
demo-namespace
backend
frontend
```

## Cach mo frontend

Dung port-forward:

```bash
kubectl -n demo port-forward svc/frontend 8080:80
```

Sau do mo:

```text
http://localhost:8080
```

Trang frontend se hien:

```text
Frontend is running
hello from backend
```

Dong `hello from backend` la ket qua frontend goi sang backend qua `/api/`.

## Validate tren Pull Request

Workflow:

```text
.github/workflows/validate.yml
```

se chay khi PR co thay doi trong:

```text
k8s/**
```

No dung `kubeconform` de kiem tra manifest Kubernetes:

```bash
kubeconform -strict -summary k8s/
```

Muc dich la chan manifest sai schema truoc khi merge vao `main`.

## Ket luan

Luon nho luong chay:

```text
Git -> ArgoCD root -> app con -> Kubernetes resources
```

Trong repo nay:

```text
root.yaml
  -> argocd/apps/namespace.yaml
  -> argocd/apps/backend.yaml
  -> argocd/apps/frontend.yaml
```

va cac app con do se tao resource that trong namespace `demo`.
