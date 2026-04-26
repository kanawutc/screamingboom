"""SimHash: 64-bit locality-sensitive hashing for near-duplicate detection.

SimHash produces fingerprints where similar texts have fingerprints with
small Hamming distance. Documents with Hamming distance ≤ 3 bits are
considered near-duplicates (~95% similarity).
"""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")

# FNV-1a constants for 64-bit
_FNV_OFFSET = 14695981039346656037
_FNV_PRIME = 1099511628211
_MASK_64 = (1 << 64) - 1


def _fnv1a_64(data: bytes) -> int:
    """FNV-1a 64-bit hash."""
    h = _FNV_OFFSET
    for byte in data:
        h ^= byte
        h = (h * _FNV_PRIME) & _MASK_64
    return h


def _shingles(text: str, size: int = 3) -> list[str]:
    """Generate character n-gram shingles from text."""
    text = _WS_RE.sub(" ", text.lower()).strip()
    if len(text) < size:
        return [text] if text else []
    return [text[i : i + size] for i in range(len(text) - size + 1)]


def simhash(text: str, shingle_size: int = 3) -> int:
    """Compute 64-bit SimHash fingerprint from text.

    Args:
        text: Input text to fingerprint.
        shingle_size: Character n-gram size (default 3).

    Returns:
        64-bit integer fingerprint.
    """
    tokens = _shingles(text, shingle_size)
    if not tokens:
        return 0

    v = [0] * 64
    for token in tokens:
        h = _fnv1a_64(token.encode("utf-8"))
        for i in range(64):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two 64-bit fingerprints."""
    return bin(a ^ b).count("1")


def find_clusters(
    items: list[tuple[str, int]],
    threshold: int = 3,
) -> list[list[str]]:
    """Group item IDs by SimHash proximity using Union-Find.

    Args:
        items: List of (id, simhash_value) tuples.
        threshold: Maximum Hamming distance for near-duplicate (default 3).

    Returns:
        List of clusters, each a list of IDs. Only clusters with ≥2 items.
    """
    if len(items) < 2:
        return []

    # Union-Find
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a_id: str, b_id: str) -> None:
        ra, rb = find(a_id), find(b_id)
        if ra != rb:
            parent[ra] = rb

    # O(n²) pairwise comparison — fine for < 50k URLs
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            id_a, hash_a = items[i]
            id_b, hash_b = items[j]
            if hamming_distance(hash_a, hash_b) <= threshold:
                union(id_a, id_b)

    # Build clusters
    clusters: dict[str, list[str]] = {}
    for item_id, _ in items:
        root = find(item_id)
        clusters.setdefault(root, []).append(item_id)

    return [ids for ids in clusters.values() if len(ids) >= 2]
