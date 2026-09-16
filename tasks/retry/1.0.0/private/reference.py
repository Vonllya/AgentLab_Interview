class TransientError(Exception):
    pass


class LocalTool:
    def __init__(self, failures):
        self.failures = list(failures)
        self.records = []
        self.cache = {}
        self.calls = 0

    def write(self, key, value):
        self.calls += 1
        failure = self.failures.pop(0) if self.failures else "ok"
        if failure == "before":
            raise TransientError("写入前暂时失败")
        if key not in self.cache:
            self.records.append(value)
            self.cache[key] = len(self.records)
        result = self.cache[key]
        if failure == "after":
            raise TransientError("写入成功但响应丢失")
        return result


def operate(tool, operation_id, value, attempts=5):
    for attempt in range(attempts):
        try:
            return tool.write(operation_id, value)
        except TransientError:
            if attempt == attempts - 1:
                raise


def scenario(data):
    tool = LocalTool(data["failures"])
    results = [operate(tool, op["id"], op["value"]) for op in data["operations"]]
    return {"records": tool.records, "results": results, "calls": tool.calls}
