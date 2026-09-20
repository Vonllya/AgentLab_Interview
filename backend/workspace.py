import ast
import difflib
import hashlib
import json
import re
import time
from pathlib import Path
from . import storage as s

MAX_CODE = 65536


def permissions(session):
    manifest=json.loads((s.package(session)/'manifest.json').read_text())
    rules={key:manifest.get(key, default) for key,default in (
        ('readable',['solution.py']),('editable',['solution.py']),('runtime',[]))}
    for names in rules.values():
        if not isinstance(names,list) or len(names)!=len(set(names)) or any(not re.fullmatch(r'[a-z][a-z0-9_]*\.py',name) for name in names):
            raise ValueError('任务文件权限清单无效')
    if set(rules['editable']) & set(rules['runtime']) or set(rules['readable']) != set(rules['editable']) | set(rules['runtime']) or 'solution.py' not in rules['readable']:
        raise ValueError('任务文件角色不完整或冲突')
    return rules


def safe_file(session, name):
    rules=permissions(session)
    if name not in rules['readable']:
        raise ValueError('文件不在任务读取白名单')
    base=s.DATA/'workspaces'/session['id']
    root=s.DATA/session['workspace']
    if base.is_symlink() or not root.resolve().is_relative_to(base.resolve()):
        raise ValueError('拒绝符号链接与越界路径')
    # Check every component, including revision ancestors.
    for ancestor in (root,*root.parents):
        if ancestor==s.DATA: break
        if ancestor.is_symlink(): raise ValueError('拒绝符号链接与越界路径')
    if name in rules['runtime']:
        root=s.package(session)/'initial'
    file=root/name
    if root.is_symlink() or file.is_symlink() or file.resolve().parent!=root.resolve():
        raise ValueError('拒绝符号链接与越界路径')
    return file


def create(task_id):
    task=s.get('task',task_id)
    id=s.ident()
    session=dict(id=id,task_id=task_id,version=task['version'],status='active',created=time.time(),hint_level=0,diagnosis='',workspace=f'workspaces/{id}')
    rules=permissions(session)
    path=s.DATA/session['workspace']; path.mkdir(parents=True)
    for name in rules['editable']:
        (path/name).write_text((s.package(session)/'initial'/name).read_text())
    s.put('session',id,session)
    return session


def read(session):
    return safe_file(session,'solution.py').read_text()


def read_all(session):
    return {name:safe_file(session,name).read_text() for name in sorted(permissions(session)['readable'])}


def save_files(session, files, diagnosis):
    rules=permissions(session)
    if set(files)!=set(rules['editable']):
        raise ValueError('必须同时保存全部可编辑文件，不得提交只读或未列出文件')
    for name,code in files.items():
        safe_file(session,name)
        if not isinstance(code,str) or len(code.encode())>MAX_CODE:
            raise ValueError('每个代码文件不得超过 64 KiB')
    if rules['readable']==['solution.py']:
        target=safe_file(session,'solution.py'); temporary=target.with_name('.save-'+s.ident())
        try:
            temporary.write_text(files['solution.py']); temporary.replace(target)
        finally: temporary.unlink(missing_ok=True)
    else:
        # A complete revision is prepared before a single SQLite pointer update.
        relative=f"workspaces/{session['id']}/{s.ident()}"
        revision=s.DATA/relative; revision.mkdir()
        for name,code in files.items(): (revision/name).write_text(code)
        session['workspace']=relative
    session['diagnosis']=diagnosis
    s.put('session',session['id'],session)


def save(session, code, diagnosis):
    save_files(session,{'solution.py':code},diagnosis)


def snapshot_contents(session, digest):
    if not re.fullmatch('[a-f0-9]{64}',digest): raise ValueError('快照标识无效')
    folder=s.DATA/'snapshots'/digest
    names=permissions(session)['readable']
    if folder.is_symlink() or set(p.name for p in folder.iterdir())!=set(names):
        raise ValueError('快照文件范围无效')
    contents={}
    for name in sorted(names):
        path=folder/name
        if path.is_symlink() or not path.is_file() or path.resolve().parent!=folder.resolve():
            raise ValueError('快照文件路径无效')
        contents[name]=path.read_text()
    for name in permissions(session)['runtime']:
        if contents[name]!=(s.package(session)/'initial'/name).read_text():
            raise ValueError('只读运行资产已改变')
    return contents


def snapshot(session):
    contents=read_all(session)
    identity=session['task_id']+'@'+session['version']+'\0'
    # Preserve legacy hashes exactly; the new format includes ordered paths and bytes.
    body=contents['solution.py'] if list(contents)==['solution.py'] else json.dumps(sorted(contents.items()),ensure_ascii=False,separators=(',',':'))
    digest=hashlib.sha256((identity+body).encode()).hexdigest()
    folder=s.DATA/'snapshots'/digest
    if folder.exists():
        if snapshot_contents(session,digest)!=contents: raise ValueError('快照内容冲突')
    else:
        folder.mkdir(parents=True)
        for name,code in contents.items():
            path=folder/name; path.write_text(code); path.chmod(0o444)
    return digest


def diff(session, digest=None):
    contents=snapshot_contents(session,digest) if digest else read_all(session)
    return ''.join(''.join(difflib.unified_diff((s.package(session)/'initial'/name).read_text().splitlines(True),contents[name].splitlines(True),fromfile='initial/'+name,tofile='saved/'+name)) for name in sorted(permissions(session)['editable']))


def constraints(session, code):
    if session['task_id'] in ('rag','rag_versioning') or session['task_id'].startswith('gen_'):
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
