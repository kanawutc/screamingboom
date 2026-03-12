"""URL normalization and hashing utilities for crawl deduplication."""

import hashlib
from urllib.parse import urljoin, urlparse, urlunparse, unquote, quote

# Schemes we allow crawling
_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Schemes we explicitly reject (common non-HTTP schemes found in href attributes)
_REJECTED_SCHEMES = frozenset(
    {
        "javascript",
        "data",
        "mailto",
        "tel",
        "ftp",
        "ftps",
        "blob",
        "file",
        "magnet",
        "ssh",
        "irc",
    }
)


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """Normalize a URL for consistent deduplication.

    Returns the normalized URL string, or None if the URL should be rejected
    (e.g. javascript:, mailto:, data: schemes).

    Steps:
      1. Resolve relative URL against base_url (if provided)
      2. Reject non-HTTP(S) schemes
      3. Lowercase scheme and host
      4. Strip fragment (#anchor)
      5. Normalize empty path to "/"
      6. Reassemble
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    # Resolve relative URLs against base
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # Reject non-HTTP schemes
    if scheme not in _ALLOWED_SCHEMES:
        return None

    # Lowercase netloc (host:port)
    netloc = parsed.netloc.lower()
    if not netloc:
        return None

    # Normalize path: decode then re-encode to canonical form
    path = parsed.path
    if not path:
        path = "/"

    # Decode unnecessary percent-encoding, then re-encode only what's needed
    path = unquote(path)
    # Re-encode, keeping safe characters that don't need encoding in paths
    path = quote(path, safe="/:@!$&'()*+,;=-._~")

    # Strip fragment entirely
    # Keep query string as-is (important for URLs like ?page=2)
    query = parsed.query

    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def url_hash(normalized_url: str) -> bytes:
    """Compute MD5 hash of a normalized URL.

    Returns 16 bytes matching the BYTEA url_hash column in the database.
    """
    return hashlib.md5(normalized_url.encode("utf-8")).digest()


def url_hash_hex(normalized_url: str) -> str:
    """Compute MD5 hex digest of a normalized URL.

    Returns 32-char hex string, useful for Bloom filter keys.
    """
    return hashlib.md5(normalized_url.encode("utf-8")).hexdigest()


def extract_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL.

    Returns lowercase host:port string.
    """
    return urlparse(url).netloc.lower()
