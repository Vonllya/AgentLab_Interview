def answer(documents, order):
    selected = [documents[i] for i in order]
    return [{"text": doc["text"], "citation": documents[i]["id"]}
            for i, doc in enumerate(selected)]


def scenario(data):
    return answer(data["documents"], data["order"])
