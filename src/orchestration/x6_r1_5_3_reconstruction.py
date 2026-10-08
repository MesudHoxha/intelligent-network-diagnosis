"""Content-bound reconstruction reuse, confined to one read-only invocation."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import hashlib
import hmac
import secrets

from src.orchestration.x6_r1_5_1_contract import canonical, load, require

_ACTIVE = ContextVar("r153_reconstruction", default=None)


def _snapshot(root):
    root = Path(root).resolve()
    if not root.exists():
        return ("ABSENT",)
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows.append((str(relative), "LINK", str(path.readlink())))
        elif path.is_file():
            rows.append((str(relative), "FILE", hashlib.sha256(path.read_bytes()).hexdigest(),
                         path.stat().st_mode & 0o777))
        elif path.is_dir():
            rows.append((str(relative), "DIR"))
    return tuple(rows)


class _Invocation:
    def __init__(self, root):
        from src.orchestration.x6_r1_5_3_campaign import source_identity
        self.root = Path(root).resolve()
        self.source = source_identity()
        self.watched = {}
        self.entries = {}
        self.pending = set()
        self.secret = secrets.token_bytes(32)
        self.watch(self.root)

    def watch(self, root):
        root = Path(root).resolve()
        snapshot = _snapshot(root)
        if root in self.watched:
            require(self.watched[root] == snapshot, "changed reconstruction inputs")
        else:
            self.watched[root] = snapshot

    def check(self):
        from src.orchestration.x6_r1_5_3_campaign import source_identity
        require(self.source == source_identity(), "changed reconstruction source")
        for root, snapshot in self.watched.items():
            require(snapshot == _snapshot(root), "changed reconstruction inputs")

    def validated(self, operation, binding, validate):
        key = canonical({"operation": operation, "campaign_root": str(self.root),
                         "source": self.source, "binding": binding})
        self.check()
        require(key not in self.pending, "cyclic or in-progress reconstruction")
        if key in self.entries:
            data, seal = self.entries[key]
            require(hmac.compare_digest(seal, hmac.digest(self.secret, key + data, "sha256")),
                    "forged reconstruction result")
            import json
            return json.loads(data)
        self.pending.add(key)
        try:
            value = validate()
            self.check()
            data = canonical(value)
            self.entries[key] = (data, hmac.digest(self.secret, key + data, "sha256"))
            return value
        finally:
            self.pending.remove(key)


@contextmanager
def reconstruction(root):
    current = _ACTIVE.get()
    root = Path(root).resolve()
    if current is not None:
        require(current.root == root, "cross-campaign reconstruction reuse")
        current.check()
        yield current
        return
    current = _Invocation(root)
    token = _ACTIVE.set(current)
    try:
        yield current
        current.check()
        require(not current.pending, "incomplete reconstruction")
    finally:
        current.entries.clear()
        _ACTIVE.reset(token)


def invocation(function):
    @wraps(function)
    def checked(root, *args, **kwargs):
        with reconstruction(root):
            return function(root, *args, **kwargs)
    return checked


def validated(root, operation, binding, validate, *, external_roots=()):
    current = _ACTIVE.get()
    if current is not None:
        require(current.root == Path(root).resolve(), "cross-campaign reconstruction reuse")
        # Registration can execute caller-supplied iteration and reads. The
        # full check inside current.validated therefore remains AFTER it and
        # immediately before accepting a reused result. A nested context-entry
        # check here would protect the same inputs before that work, then
        # repeat the full scan without accepting any result in between.
        for path in external_roots:
            current.watch(path)
        return current.validated(operation, binding, validate)
    with reconstruction(root) as current:
        for path in external_roots:
            current.watch(path)
        return current.validated(operation, binding, validate)
