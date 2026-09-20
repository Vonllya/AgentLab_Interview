import json
import os
import re
import selectors
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from .execution_diagnostics import typed_error

IMAGE = os.getenv('AGENTLAB_IMAGE','agentlab-runner:0.1')


def diagnose():
    """Do not confuse missing CLI, daemon access, and a missing task image."""
    result = {'status': 'unknown', 'cli': False, 'daemon': None, 'image': None}
    def finish(status, reason):
        return dict(result, status=status, reason=reason)
    if not shutil.which('docker'):
        return finish('cli_missing', '未安装 Docker CLI，或 CLI 不在当前 PATH；服务与镜像尚未检查。参见 docs/DOCKER_SETUP.md。')
    try:
        client = subprocess.run(['docker', '--version'], capture_output=True, timeout=5)
        if client.returncode:
            return finish('cli_error', 'Docker CLI 无法正常执行；服务与镜像尚未检查。')
        result['cli'] = True
        server = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture_output=True, timeout=5)
        if server.returncode:
            result['daemon'] = False
            message = (server.stderr + server.stdout).decode(errors='replace').lower()
            if any(word in message for word in ('permission denied', 'access is denied', 'operation not permitted')):
                return finish('permission_denied', 'Docker 服务访问权限不足（也可能受当前沙箱限制）；不等同于服务未启动。')
            if any(word in message for word in ('cannot connect', 'connection refused', 'no such file or directory', 'is the docker daemon running')):
                return finish('daemon_unreachable', 'Docker 服务连接不可达；可能未启动、WSL 集成未启用或 context/DOCKER_HOST 配置错误。')
            return finish('daemon_error', 'Docker 服务检查失败；请在同一终端运行 docker info 检查 context、TLS 或服务错误。')
        result['daemon'] = True
        image = subprocess.run(['docker', 'image', 'inspect', IMAGE], capture_output=True, timeout=5)
        if image.returncode:
            result['image'] = False
            message = (image.stderr + image.stdout).decode(errors='replace').lower()
            if 'no such image' in message or 'no such object' in message:
                return finish('image_missing', 'Docker 服务可用，但任务镜像不存在；请构建 backend/Dockerfile。')
            if 'permission denied' in message or 'access is denied' in message:
                return finish('permission_denied', 'Docker 镜像检查被权限拒绝。')
            return finish('image_error', 'Docker 镜像检查失败；不应将此错误认定为任务行为失败。')
    except PermissionError:
        return finish('permission_denied', '当前环境没有执行 Docker CLI 或访问服务的权限。')
    except subprocess.TimeoutExpired:
        return finish('check_timeout', 'Docker 可用性检查超时；服务或镜像状态尚未确认。')
    except OSError:
        return finish('cli_error', 'Docker CLI 执行错误。')
    result['image'] = True
    return finish('ready', '')


def availability():
    result = diagnose()
    return result['status'] == 'ready', result['reason']


def docker_command(folder, name, image_id=None):
    if image_id is not None and not re.fullmatch('sha256:[a-f0-9]{64}',image_id):
        raise ValueError('只能使用服务端冻结的本地镜像摘要')
    run_id=os.getenv('AGENTLAB_RUN_ID','')
    labels=['--label','agentlab.run='+run_id] if re.fullmatch('[a-f0-9]{32}',run_id) else []
    return ['docker','run','--rm','--name',name,'--label','agentlab=true', *labels,
            '--network','none','--read-only','--user','65534:65534',
            '--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','128m','--memory-swap','128m','--cpus','0.5',
            '--pids-limit','32','--ulimit','nofile=64:64',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777',
            '--mount',f'type=bind,src={folder.resolve()},dst=/workspace,readonly',
            *(['--pull','never'] if image_id else []),'-i',image_id or IMAGE]


def cleanup_run(run_id):
    if not re.fullmatch('[a-f0-9]{32}',run_id) or not shutil.which('docker'):
        return
    try:
        found=subprocess.run(['docker','ps','-aq','--filter','label=agentlab.run='+run_id],capture_output=True,text=True,timeout=5)
        ids=[line for line in found.stdout.splitlines() if re.fullmatch('[a-f0-9]{12,64}',line)]
        if ids:
            subprocess.run(['docker','rm','-f',*ids],capture_output=True,timeout=5)
    except (OSError,subprocess.TimeoutExpired):
        pass


def execute(folder, payload, timeout=8, allowed_files=None, image_id=None):
    folder=Path(folder)
    file=folder/'solution.py'
    allowed=set(allowed_files or ['solution.py'])
    if 'solution.py' not in allowed or any(not re.fullmatch(r'[a-z][a-z0-9_]*\.py',name) for name in allowed):
        raise ValueError('非法运行文件清单')
    if folder.is_symlink() or set(p.name for p in folder.iterdir())!=allowed:
        raise ValueError('非法执行快照')
    if any((folder/name).is_symlink() or not (folder/name).is_file() or (folder/name).resolve().parent!=folder.resolve() for name in allowed):
        raise ValueError('非法执行快照')
    name='agentlab-'+uuid.uuid4().hex
    proc=None
    start=time.monotonic()
    output=bytearray()
    try:
        proc=subprocess.Popen(docker_command(folder,name,image_id),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        proc.stdin.write(json.dumps(payload).encode())
        proc.stdin.close()
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout,selectors.EVENT_READ)
            while sel.get_map():
                if time.monotonic()-start>timeout:
                    raise typed_error(TimeoutError, f'容器执行超过 {timeout:g} 秒', 'execution_timeout', 'execution', timeout_seconds=timeout)
                for key,_ in sel.select(.1):
                    chunk=os.read(key.fileobj.fileno(),4096)
                    if not chunk:
                        sel.unregister(key.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output)>32768:
                            raise typed_error(ValueError, '执行输出超过 32 KiB', 'output_limit', 'transport', limit_bytes=32768)
        proc.wait(timeout=1)
        if proc.returncode:
            raise typed_error(RuntimeError, '容器异常退出 '+str(proc.returncode), 'container_exit', 'container', exit_code=proc.returncode, possible_start_failure=proc.returncode in (125,126,127), cause='unknown')
        try:
            return json.loads(output)
        except (ValueError,UnicodeDecodeError):
            raise typed_error(ValueError, '用户程序未返回有效的单个 JSON；请移除调试输出', 'invalid_json', 'transport')
    except OSError as exc:
        if hasattr(exc,'diagnostic'):raise
        raise typed_error(RuntimeError, 'Docker 进程通信或启动失败', 'docker_cli_missing' if isinstance(exc,FileNotFoundError) else 'docker_permission_denied' if isinstance(exc,PermissionError) else 'container_io_error', 'docker_cli' if proc is None else 'transport', exception_type=type(exc).__name__) from exc
    finally:
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        try:
            subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        except (OSError,subprocess.TimeoutExpired):
            pass
