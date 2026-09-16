import json
import os
import re
import selectors
import shutil
import subprocess
import time
import uuid
from pathlib import Path

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


def docker_command(folder, name):
    run_id=os.getenv('AGENTLAB_RUN_ID','')
    labels=['--label','agentlab.run='+run_id] if re.fullmatch('[a-f0-9]{32}',run_id) else []
    return ['docker','run','--rm','--name',name,'--label','agentlab=true', *labels,
            '--network','none','--read-only','--user','65534:65534',
            '--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','128m','--memory-swap','128m','--cpus','0.5',
            '--pids-limit','32','--ulimit','nofile=64:64',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=16m,mode=1777',
            '--mount',f'type=bind,src={folder.resolve()},dst=/workspace,readonly',
            '-i',IMAGE]


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


def execute(folder, payload, timeout=8):
    folder=Path(folder)
    file=folder/'solution.py'
    if folder.is_symlink() or file.is_symlink() or set(p.name for p in folder.iterdir())!={'solution.py'}:
        raise ValueError('非法执行快照')
    name='agentlab-'+uuid.uuid4().hex
    proc=None
    start=time.monotonic()
    output=bytearray()
    try:
        proc=subprocess.Popen(docker_command(folder,name),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        proc.stdin.write(json.dumps(payload).encode())
        proc.stdin.close()
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout,selectors.EVENT_READ)
            while sel.get_map():
                if time.monotonic()-start>timeout:
                    raise TimeoutError(f'容器执行超过 {timeout:g} 秒')
                for key,_ in sel.select(.1):
                    chunk=os.read(key.fileobj.fileno(),4096)
                    if not chunk:
                        sel.unregister(key.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output)>32768:
                            raise ValueError('执行输出超过 32 KiB')
        proc.wait(timeout=1)
        if proc.returncode:
            raise RuntimeError('容器异常退出 '+str(proc.returncode))
        try:
            return json.loads(output)
        except (ValueError,UnicodeDecodeError):
            raise ValueError('用户程序未返回有效的单个 JSON；请移除调试输出')
    finally:
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        try:
            subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        except (OSError,subprocess.TimeoutExpired):
            pass
