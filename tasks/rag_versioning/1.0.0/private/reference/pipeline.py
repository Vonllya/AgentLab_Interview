"""场景 actions: import(document_id, version, body)、query(query, limit=1)、reopen。
trace 为诊断记录而非判分结果；query 的 limit 为正整数。
"""
from ingestion import split_document
from index_store import IndexStore
from retrieval import search
from context_builder import build_context


def run(data, path):
    store = IndexStore(path)
    queries, trace = [], []
    try:
        for action in data['actions']:
            if action['op'] == 'import':
                doc, version = action['document_id'], action['version']
                before = store.count(doc)
                store.update(doc, version, split_document(doc, version, action['body']))
                trace.append(dict(kind='import', document_id=doc, input_version=version,
                                  chunks_before=before, chunks_after=store.count(doc)))
            elif action['op'] == 'reopen':
                store.close()
                store = IndexStore(path)
                trace.append(dict(kind='reopen'))
            elif action['op'] == 'query':
                candidates = search(store, action['query'])
                context = build_context(action['query'], candidates[:action.get('limit', 1)])
                queries.append(context)
                trace.append(dict(kind='query', candidates=candidates, context=context))
        return dict(queries=queries, trace=trace)
    finally:
        store.close()
