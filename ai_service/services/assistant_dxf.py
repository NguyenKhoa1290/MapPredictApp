"""Cache detached summaries, never retain complete drawings between chats."""
from collections import OrderedDict
import gc
import hashlib
import json
import threading
import time

import ezdxf

CACHE = OrderedDict()
LOCK = threading.RLock()
MAX_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 16
TTL = 900


def prune():
    with LOCK:
        for key, value in list(CACHE.items()):
            if time.monotonic() - value[0] >= TTL:
                del CACHE[key]


class PreviewDrawing:
    def __init__(self, path, data):
        self.path = path
        self.key = hashlib.sha256(data).hexdigest()
        self.large = len(data) > 2 * 1024 * 1024
        self.document = None
        self.cache_hit = False

    def summary(self):
        with LOCK:
            cached = CACHE.get(self.key)
            if cached and time.monotonic() - cached[0] < TTL:
                CACHE.move_to_end(self.key)
                self.cache_hit = True
                return json.loads(cached[1])
        from .assistant import describe
        document = ezdxf.readfile(self.path)
        result = describe(document)
        del document
        if self.large:
            gc.collect()  # Drawings contain cycles; release them before waiting for the LLM.
        encoded = json.dumps(result, ensure_ascii=True, separators=(',', ':')).encode('ascii')
        if len(encoded) <= MAX_BYTES:
            with LOCK:
                CACHE[self.key] = (time.monotonic(), encoded)
                CACHE.move_to_end(self.key)
                while len(CACHE) > MAX_ITEMS or sum(len(item[1]) for item in CACHE.values()) > MAX_BYTES:
                    CACHE.popitem(last=False)
        return result

    @property
    def entitydb(self):
        # Only mutation proposals require a full document for exact validation.
        # Apply still reopens the original file and verifies its signed hash.
        if self.document is None:
            self.document = ezdxf.readfile(self.path)
        return self.document.entitydb
