import ast
import hashlib
import json
import time
from pathlib import Path
from . import storage as s

MAX_CODE = 65536


def safe_file(session, name):
    if name != 'solution.py':
        raise ValueError('只允许访问 solution.py')
    root = s.DATA / 'workspaces' / session['id']
    file = root / name
    if root.is_symlink() or file.is_symlink() or file.resolve().parent != root.resolve():
        raise ValueError('拒绝符号链接与越界路径')
    return file


def create(task_id):
    task = s.get('task',task_id)
    id = s.ident()
    session = dict(id=id,task_id=task_id,version=task['version'],status='active',created=time.time(),hint_level=0,diagnosis='',workspace=f'workspaces/{id}')
    path = s.DATA / 'workspaces' / id
    path.mkdir(parents=True)
    (path/'solution.py').write_text((s.package(session)/'initial/solution.py').read_text())
    s.put('session',id,session)
    return session


def read(session):
    return safe_file(session,'solution.py').read_text()


def save(session, code, diagnosis):
    if len(code.encode()) > MAX_CODE:
        raise ValueError('代码超过 64 KiB')
    target=safe_file(session,'solution.py')
    temporary=target.with_name('.save-'+s.ident())
    try:
        temporary.write_text(code)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    session['diagnosis'] = diagnosis
    s.put('session',session['id'],session)


def snapshot(session):
    code = read(session)
    digest = hashlib.sha256((session['task_id']+'@'+session['version']+'\0'+code).encode()).hexdigest()
    folder = s.DATA/'snapshots'/digest
    folder.mkdir(parents=True,exist_ok=True)
    path = folder/'solution.py'
    if path.exists() and path.read_text()!=code:
        raise ValueError('快照内容冲突')
    if not path.exists():
        path.write_text(code)
        path.chmod(0o444)
    return digest


def constraints(session, code):
    if session['task_id']=='rag':
        return []
    allowed = 'operate' if session['task_id']=='retry' else 'resume'
    original = (s.package(session)/'initial/solution.py').read_text()
    def fixed(text):
        tree = ast.parse(text)
        return [ast.dump(n,include_attributes=False) for n in tree.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) or n.name!=allowed]
    try:
        if fixed(original)!=fixed(code):
            return [f'只允许修改 {allowed} 函数；模拟服务和协议不可修改']
    except SyntaxError:
        return ['Python 语法错误']
    return []
