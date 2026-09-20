"""只读场景入口。每次调用使用独立临时 SQLite；不依赖跨调用目录。
业务模块须保留公开接口及 documents/chunks 表协议，可查看各模块定义。
result 是供宿主比较的行为数据，trace 是可被业务代码影响的诊断记录。
"""
import sqlite3
import tempfile
from pathlib import Path
from pipeline import run


def scenario(data):
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / 'index.sqlite3')
        output = run(data, path)
        with sqlite3.connect(path) as db:
            versions = dict(db.execute('SELECT document_id, version FROM documents ORDER BY document_id'))
            rows = db.execute('SELECT chunk_id, document_id, version, position, text FROM chunks ORDER BY document_id, version, position').fetchall()
        chunks = [dict(zip(('chunk_id', 'document_id', 'version', 'position', 'text'), row)) for row in rows]
        return {'result': {'queries': output['queries'], 'versions': versions, 'chunks': chunks}, 'trace': output['trace']}
