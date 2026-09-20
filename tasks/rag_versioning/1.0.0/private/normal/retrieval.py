"""固定词项匹配：query 按空白分词，分数为出现在片段中的词项数。
分数相同按 document_id、version、position 升序，保证可复现实验。
"""


def search(store, query):
    terms = query.split()
    candidates = []
    for chunk in store.all_chunks():
        score = sum(term in chunk['text'] for term in terms)
        if score:
            candidates.append(dict(chunk, score=score))
    return sorted(candidates, key=lambda item: (-item['score'], item['document_id'], item['version'], item['position']))
