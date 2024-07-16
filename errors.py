import traceback


def _ok(result=None):
    if result is not None:
        return {"ok": True, "result": result}
    else:
        return {"ok": True}


def _exception(exception):
    exc_info = traceback.format_exc()
    return {
        "ok": False,
        "error": "Unhandled exception",
        "exception": exception.__class__.__name__,
        "description": str(exception.args[0] if exception.args else exception),
        "traceback": exc_info,
    }


def _error(data, message):
    return {
        "ok": False,
        "data": data,
        "description": message,
    }


def _fail(message):
    return {
        "ok": False,
        "error": "Operation failed",
        "description": message,
    }


