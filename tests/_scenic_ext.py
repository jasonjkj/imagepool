"""test_scenic 用的外部 provider 桩（演示「使用者提供函数」契约）。"""


def alpha(query, ctx, opts):
    return ["http://alpha.example/1.jpg", "http://alpha.example/2.jpg"]


def boom(query, ctx, opts):
    raise RuntimeError("provider boom")


def local(query, ctx, opts):
    return [{"ref": "/tmp/scenic-ext-local.jpg", "local": True}]


def empty(query, ctx, opts):
    return []


def verify_ok(path, ctx):
    return True


def verify_bad(path, ctx):
    return False
