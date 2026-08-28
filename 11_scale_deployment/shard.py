import hashlib
from typing import List, Dict, Any


def get_camera_shard(camera_id: str, shard_count: int) -> int:
    """
    Computes deterministic shard assignment for a camera ID using consistent hashing.
    Always assigns the same camera_id to the exact same shard index (0 <= index < shard_count).
    """
    if shard_count <= 1:
        return 0
    # MD5 hash of camera_id as integer
    digest = hashlib.md5(camera_id.encode("utf-8")).hexdigest()
    hash_val = int(digest, 16)
    return hash_val % shard_count


def is_camera_assigned_to_shard(camera_id: str, shard_index: int, shard_count: int) -> bool:
    """Returns True if the camera belongs to the specified shard."""
    if shard_count <= 1:
        return shard_index == 0
    return get_camera_shard(camera_id, shard_count) == shard_index


def filter_cameras_for_shard(
    camera_ids: List[str],
    shard_index: int,
    shard_count: int
) -> List[str]:
    """Filters a list of camera IDs, returning only those assigned to the given shard."""
    return [cid for cid in camera_ids if is_camera_assigned_to_shard(cid, shard_index, shard_count)]


def get_shard_distribution(
    camera_ids: List[str],
    shard_count: int
) -> Dict[int, List[str]]:
    """Calculates distribution of cameras across all shards for balance inspection."""
    distribution: Dict[int, List[str]] = {s: [] for s in range(shard_count)}
    for cid in camera_ids:
        shard = get_camera_shard(cid, shard_count)
        distribution[shard].append(cid)
    return distribution
