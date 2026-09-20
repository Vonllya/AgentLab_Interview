"""完整正文按非空行确定性切分，chunk_id 包含文档 ID、整数版本和行序号。"""


def split_document(document_id, version, body):
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return [dict(chunk_id=f'{document_id}:{version}:{i}', document_id=document_id,
                 version=version, position=i, text=text) for i, text in enumerate(lines)]
