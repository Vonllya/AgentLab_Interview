"""SQLite 存储协议：documents(document_id, version)；chunks 的字段见 schema。
查询访问当前 SQLite 记录；close 后数据库应可重新打开。
"""
import sqlite3


class IndexStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS documents(document_id TEXT PRIMARY KEY, version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS chunks(chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                version INTEGER NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL);
        ''')

    def update(self, document_id, version, chunks):
        row = self.db.execute('SELECT version FROM documents WHERE document_id=?', (document_id,)).fetchone()
        if row is not None and version <= row['version']:
            return
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO documents VALUES (?, ?)', (document_id, version))
            self.db.executemany('INSERT INTO chunks VALUES (:chunk_id, :document_id, :version, :position, :text)', chunks)

    def all_chunks(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM chunks ORDER BY document_id, version, position')]

    def count(self, document_id):
        return self.db.execute('SELECT COUNT(*) FROM chunks WHERE document_id=?', (document_id,)).fetchone()[0]

    def close(self):
        self.db.close()
