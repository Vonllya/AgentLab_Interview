"""只使用选中的片段生成确定性答案与对应引用，无远程模型。"""


def build_context(query, candidates):
    return {'query': query, 'answer': '\n'.join(item['text'] for item in candidates) or '未找到相关内容',
            'citations': [{key: item[key] for key in ('chunk_id', 'document_id', 'version')} for item in candidates]}
