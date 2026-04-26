"""Cookie audit: parse Set-Cookie headers and analyze security flags."""

from __future__ import annotations

from http.cookies import SimpleCookie


def parse_set_cookies(raw_header: str, page_domain: str) -> list[dict]:
    """Parse Set-Cookie header string into structured cookie data.

    Args:
        raw_header: Raw Set-Cookie header value (may contain multiple cookies
                    separated by newlines in multi-valued headers).
        page_domain: Domain of the page setting the cookie.

    Returns:
        List of cookie dicts with name, domain, flags, and classification.
    """
    cookies = []

    # Handle multi-valued headers (joined by commas in some HTTP libraries)
    # But Set-Cookie with commas is tricky — split on common patterns
    lines = raw_header.split("\n") if "\n" in raw_header else [raw_header]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            sc = SimpleCookie()
            sc.load(line)
        except Exception:
            continue

        for name, morsel in sc.items():
            domain = morsel["domain"].strip(".") if morsel["domain"] else page_domain
            is_third_party = not _is_same_domain(domain, page_domain)

            cookie_info = {
                "name": name,
                "domain": domain,
                "path": morsel["path"] or "/",
                "secure": bool(morsel["secure"]),
                "httponly": bool(morsel["httponly"]),
                "samesite": morsel.get("samesite", ""),
                "max_age": morsel["max-age"] or None,
                "is_third_party": is_third_party,
            }

            # Flag security issues
            issues = []
            if not morsel["secure"]:
                issues.append("missing_secure")
            if not morsel["httponly"]:
                issues.append("missing_httponly")
            samesite = morsel.get("samesite", "").lower()
            if not samesite or samesite == "none":
                issues.append("samesite_none_or_missing")

            cookie_info["issues"] = issues
            cookies.append(cookie_info)

    return cookies


def _is_same_domain(cookie_domain: str, page_domain: str) -> bool:
    """Check if cookie domain matches or is a parent of page domain."""
    cookie_domain = cookie_domain.lower().strip(".")
    page_domain = page_domain.lower().strip(".")

    if cookie_domain == page_domain:
        return True
    if page_domain.endswith("." + cookie_domain):
        return True
    return False
