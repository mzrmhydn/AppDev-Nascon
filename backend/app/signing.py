# HMAC signatures and the draw-lots key, copied from spec Appendix A (§5.3, §5.10).
import hashlib
import hmac
import json

from app import config


def canonical(obj):
    """Sorted keys, no whitespace, UTF-8 (non-ASCII not escaped)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(id_, payload_obj, salt=None):
    """HMAC-SHA256(DAY1_SALT, id + "|" + canonical(payload)) as 64 lowercase hex chars."""
    key = config.DAY1_SALT if salt is None else salt
    msg = (id_ + "|" + canonical(payload_obj)).encode("utf-8")
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def lots_key(seed, league_id, team_id):
    return hashlib.sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()
