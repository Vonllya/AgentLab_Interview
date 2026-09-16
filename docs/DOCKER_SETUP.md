# Docker 验收前置条件：WSL2 / Ubuntu 22.04

## 2026-09-14：已确认是当前进程组权限未刷新

当前真实 socket 为 `root:docker`、`660`，`docker` 组 GID 为 1001。`getent group docker` 和 `id vonllya` 均显示账户已加入，但当前进程的 `id` 只有 `vonllya,sudo`。因此不再运行 usermod，不修改 socket。

本轮使用 `sg docker -c '…'` 在普通用户 UID 1000 的新子进程中依次运行 Docker 与验收。实测子进程保留 sudo/vonllya 组，获得 docker 组，`docker info` 成功返回 Server 29.7.2。这不会更新现有 Codex、终端或后端的组权限。

日常永久刷新步骤：

1. 保存工作，正常退出当前 Codex 和项目后端。
2. 关闭当前 WSL 终端，从 Windows 重新打开 Ubuntu 终端；若通过 VS Code WSL 远程连接启动，关闭远程连接后重新连接，不能只复用旧的终端服务进程。
3. 在新终端运行 `id -nG`，确认包含 `docker`；运行 `docker info`，确认 Server 可访问。
4. 从这个确认过的终端重新启动 Codex 和 `./scripts/start.sh`。

不需要 sudo 密码，也不需要再次加入组。本轮没有终止用户现有 Codex 进程；组刷新由重新启动的进程完成。临时运行单个命令时可以用 `sg docker -c 'docker info'`，但每个调用的作用域独立，不能把一次 newgrp/sg 当作后续进程已刷新。

以下保留上轮 CLI 不可用时的排查步骤作为历史与其他情况参考。


2026-09-13 本工作区检测：Ubuntu 22.04.5 LTS、WSL2 内核；`command -v docker` 无输出，`docker version` 退出 127。没有发现 `/var/run/docker.sock`、`/run/user/1000/docker.sock` 和 `/mnt/wsl/docker-desktop`；`DOCKER_HOST` / `DOCKER_CONTEXT` 未设置。

**已确认：当前 WSL 环境 Docker CLI 缺失或未接入 PATH。未确认：Windows 是否安装 Docker Desktop、其服务是否启动、镜像是否存在。不能把这些未检查项写成“服务未启动”或“权限不足”。**

## 优先使用 Windows Docker Desktop 的 WSL2 集成

1. 在 **Windows PowerShell** 运行 `wsl --list --verbose`，确认当前 Ubuntu 发行版是版本 2。若没有安装 Docker Desktop，按 [Docker 官方 Windows 安装步骤](https://docs.docker.com/desktop/setup/install/windows-install/)安装；若已安装，启动 Docker Desktop 并等待引擎就绪。
2. Docker Desktop → Settings → General，启用 **Use the WSL 2 based engine**；确认使用 Linux containers。
3. Settings → Resources → **WSL Integration**，启用列表中当前使用的 Ubuntu 发行版（名称以第 1 步输出为准），Apply & restart。重新打开该 WSL 终端。不要仅为了这个项目在同一 WSL 里再安装另一套 Engine。参见 [Docker 官方 WSL2 集成说明](https://docs.docker.com/desktop/features/wsl/)。
4. 在 **WSL Ubuntu 终端**验证：

   ```bash
   command -v docker
   docker --version
   docker context show
   docker version
   docker info
   ```

   `docker --version` 只证明 CLI 存在；`docker version` 必须看到 Server 信息，`docker info` 必须成功，才算服务可用。
5. 回到工作区构建指定任务镜像（这里只运行 Docker，不在宿主运行任务代码）：

   ```bash
   cd /home/vonllya/workspace/AgentLab_Interview
   docker build -t agentlab-runner:0.1 -f backend/Dockerfile .
   .venv/bin/python scripts/docker_check.py
   ./scripts/acceptance.sh
   ```

若 `.env` 使用自定义 `AGENTLAB_IMAGE`，在同一终端导出该变量并把镜像构建为相同 tag。验收脚本在 `data/acceptance/run-*/` 保存逐项证据；必须核对原 13 项真实 Docker 用例全部通过，以及浏览器提交闭环通过、无跳过。

## 不同错误的处理

| 检查结果 | 能确认的事实 | 操作 |
|---|---|---|
| `cli_missing` | CLI 未安装或不在 PATH；服务、镜像未检查 | 按上面的 Desktop WSL Integration 接入；先在同一个 WSL 终端使 `docker --version` 成功 |
| `daemon_unreachable` | CLI 可用但连不上服务；不一定是服务没启动 | Desktop 方案先启动 Desktop、检查集成；核对 `docker context show` / `docker context ls` 与 `DOCKER_HOST` 是否选错服务 |
| `permission_denied` | 操作被权限拒绝；服务状态不能由此推断 | 若普通 WSL 终端能连接、仅工具沙箱不能，应授权该执行环境访问，不能靠改 socket 权限解决；若原生 Engine 也报错，按下节处理组权限 |
| `image_missing` | 服务已经连通，指定 tag 不存在 | 在同一 context 下执行上面的 `docker build`；不要把镜像缺失计为题目失败 |
| `check_timeout` / `daemon_error` / `image_error` | 检查未成功完成 | 在同一终端运行 `docker info`、`docker image inspect agentlab-runner:0.1` 查看本地错误；先处理连接/TLS/context/服务问题，再验收 |

## 如果使用 Ubuntu 原生 Docker Engine

这是 Desktop 集成以外的替代方案；仅在已经选择原生 Engine 时使用。按 [官方 Ubuntu Engine 安装说明](https://docs.docker.com/engine/install/ubuntu/)配置 Docker apt 仓库并安装 Engine。安装后：

```bash
sudo systemctl start docker
systemctl is-active docker
sudo docker info
```

如果 `sudo docker info` 成功而普通 `docker info` 报 socket permission denied，再按照[官方 Linux 权限配置](https://docs.docker.com/engine/install/linux-postinstall/)处理：

```bash
sudo usermod -aG docker "$USER"
# 退出并重新登录 WSL，或在新终端运行：
newgrp docker
docker info
```

Docker 组具有宿主级管理能力，不使用 `chmod 666 /var/run/docker.sock`。若 WSL 未启用 systemd，先按发行版的 WSL systemd 配置使服务管理可用；Desktop 方案无需在 Ubuntu 内启动 `docker.service`。

## 浏览器和真实模型

标准浏览器准备命令：`frontend/node_modules/.bin/playwright install chromium`。本次已经下载的浏览器可复用：

```bash
AGENTLAB_BROWSER_EXECUTABLE=/tmp/agentlab-browser/chrome-linux64/chrome ./scripts/acceptance.sh
```

不要设置 `AGENTLAB_REUSE_SERVER`，让完整验收启动独立 mock 后端和测试数据库；避免误用正在运行的其他配置。真实供应商联调单独进行，不能将这个 mock 后端计作真实模型验证。本次未发现模型配置，未发起供应商请求，也未打印任何密钥。
