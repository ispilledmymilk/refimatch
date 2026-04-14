from __future__ import annotations

import os
from typing import Any


def try_build_langfuse_handler() -> Any | None:
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
    sk = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST")
    if not pk or not sk:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        kwargs: dict[str, Any] = {"public_key": pk, "secret_key": sk}
        if host:
            kwargs["host"] = host
        return CallbackHandler(**kwargs)
    except Exception:
        try:
            from langfuse.callback import CallbackHandler

            kwargs = {"public_key": pk, "secret_key": sk}
            if host:
                kwargs["host"] = host
            return CallbackHandler(**kwargs)
        except Exception:
            return None
