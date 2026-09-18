"""
MemoryPal v58 beta - clean startup and release prep.

This milestone records the cleanup and efficiency pass before longer testing:
build leftovers are cleaned with a dedicated script, optional imports stay lazy,
profile config reads are cached, and generated UI/icon images are reused.
"""

import time
from functools import lru_cache


class ProfileConfigCache:
    def __init__(self):
        self.value = None
        self.mtime = None

    def load(self, path, reader):
        current_mtime = path.stat().st_mtime_ns if path.exists() else None
        if self.value is not None and current_mtime == self.mtime:
            return dict(self.value)
        config = reader(path)
        self.value = dict(config)
        self.mtime = current_mtime
        return dict(config)


@lru_cache(maxsize=24)
def rendered_logo_pixels(size, scale):
    # The real app uses this idea to avoid regenerating the same icon pixels
    # every time the titlebar or navigation rail redraws.
    return tuple((x, y, size, scale) for y in range(size) for x in range(size))


class LazyFeature:
    def __init__(self, module_name):
        self.module_name = module_name
        self.module = None

    def load(self):
        if self.module is None:
            self.module = __import__(self.module_name)
        return self.module


if __name__ == "__main__":
    start = time.perf_counter()
    rendered_logo_pixels(32, 2)
    rendered_logo_pixels(32, 2)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"Cached logo render demo: {elapsed_ms:.2f} ms")
    print("Cleanup script: clean_build_artifacts.cmd")
