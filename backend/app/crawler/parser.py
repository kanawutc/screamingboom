"""HTML Parser Pool: selectolax-based extraction pipeline for SEO data.

Extracts structured page data from HTML content using selectolax (35x faster
than BeautifulSoup). Returns PageData dataclass with all SEO-relevant fields.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import structlog
from selectolax.parser import HTMLParser

from app.crawler.utils import normalize_url, extract_domain

logger = structlog.get_logger(__name__)

# Tags to remove before computing word count
_INVISIBLE_TAGS = {"script", "style", "noscript", "template", "svg", "math"}

# Whitespace normalizer
_WS_RE = re.compile(r"\s+")

# Sentence boundary regex (English-ish)
_SENTENCE_RE = re.compile(r"[.!?]+\s+|\n")

# Vowel regex for syllable estimation
_VOWELS = re.compile(r"[aeiouy]+", re.IGNORECASE)


def _count_sentences(text: str) -> int:
    """Estimate sentence count from text."""
    parts = _SENTENCE_RE.split(text)
    return max(len([p for p in parts if p.strip()]), 1)


def _count_syllables(text: str) -> int:
    """Estimate syllable count (English approximation)."""
    words = text.lower().split()
    total = 0
    for word in words:
        vowel_groups = _VOWELS.findall(word)
        count = len(vowel_groups)
        # Silent 'e' at end
        if word.endswith("e") and count > 1:
            count -= 1
        total += max(count, 1)
    return total


@dataclass
class LinkData:
    """A link found on a page."""

    url: str
    anchor_text: str
    rel_attrs: list[str]
    link_type: str  # "internal", "external", "resource"
    tag: str  # "a", "img", "link", "script", "iframe"

    def is_same_domain(self, base_domain: str) -> bool:
        try:
            link_domain = urlparse(self.url).netloc.lower()
            return link_domain == base_domain or link_domain.endswith(f".{base_domain}")
        except Exception:
            return False


@dataclass
class ImageData:
    """An image found on a page."""

    src: str
    alt: str
    srcset: str | None = None
    width: str | None = None
    height: str | None = None


@dataclass
class PaginationData:
    """Pagination rel=next/prev data."""

    rel_next: str | None = None
    rel_prev: str | None = None


@dataclass
class HreflangData:
    """An hreflang tag."""

    hreflang: str
    href: str


@dataclass
class PageData:
    """Extracted data from a single HTML page."""

    title: str | None = None
    title_length: int | None = None
    meta_description: str | None = None
    meta_desc_length: int | None = None
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    canonical_url: str | None = None
    robots_meta: list[str] = field(default_factory=list)
    is_indexable: bool = True
    indexability_reason: str | None = None
    word_count: int = 0
    content_hash: bytes = b""
    simhash: int = 0  # 64-bit SimHash fingerprint for near-duplicate detection
    links: list[LinkData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)
    hreflang_tags: list[HreflangData] = field(default_factory=list)
    structured_data_blocks: list[dict] = field(default_factory=list)
    og_tags: dict = field(default_factory=dict)

    # Sprint 2 additions
    title_count: int = 0
    meta_desc_count: int = 0
    canonical_count: int = 0
    robots_meta_tag_count: int = 0
    heading_sequence: list[str] = field(default_factory=list)  # ["h1","h2","h2","h3",...]
    mixed_content_urls: list[str] = field(default_factory=list)

    # Pagination attributes
    pagination: PaginationData | None = None
    pagination_count: dict = field(default_factory=dict)  # {"next": N, "prev": N}

    # Phase 2.11: Content analysis
    text_ratio: float = 0.0  # text-to-html ratio (0-1)
    readability_score: float | None = None  # Flesch Reading Ease (0-100)
    avg_words_per_sentence: float = 0.0

    # Phase 3E: Custom extraction rules results
    custom_extractions: dict = field(default_factory=dict)
    custom_search_results: dict = field(default_factory=dict)


class ParserPool:
    """Stateless HTML parser using selectolax.

    Usage::

        parser = ParserPool()
        page_data = parser.parse(html_bytes, base_url="https://example.com/page")
    """

    def parse(
        self,
        html_content: bytes | str,
        base_url: str,
        content_type_header: str | None = None,
        custom_extractors: list[dict] | None = None,
        custom_searches: list[dict] | None = None,
    ) -> PageData:
        """Parse HTML and extract all SEO-relevant data.

        Args:
            html_content: Raw HTML bytes or string.
            base_url: The URL this page was fetched from (for resolving relative URLs).
            content_type_header: Content-Type header value (for charset detection).
            custom_extractors: List of dicts representing extraction rules.
            custom_searches: List of dicts representing search rules.

        Returns:
            PageData dataclass with all extracted fields.
        """
        # Decode bytes to string if needed
        if isinstance(html_content, bytes):
            html_str = self._decode_html(html_content, content_type_header)
        else:
            html_str = html_content

        tree = HTMLParser(html_str)
        base_domain = extract_domain(base_url)

        data = PageData()

        # Follow the defined extraction order from PLAN.md
        self._extract_title(tree, data)
        self._extract_meta_description(tree, data)
        self._extract_robots_meta(tree, data)
        self._extract_canonical(tree, data, base_url)
        self._extract_headings(tree, data)
        self._extract_links(tree, data, base_url, base_domain)
        self._extract_images(tree, data, base_url)
        self._extract_hreflang(tree, data, base_url)
        self._extract_pagination(tree, data, base_url)
        self._extract_structured_data(tree, data, base_url)
        self._extract_og_tags(tree, data)

        # Content cleanup and metrics
        self._compute_word_count(tree, data)
        self._compute_content_hash(html_str, data)

        # Mixed content detection (HTTPS pages loading HTTP resources)
        self._detect_mixed_content(tree, data, base_url)

        # Determine indexability from robots meta
        self._determine_indexability(data)

        # Phase 3E: Apply custom rules
        if custom_extractors:
            self._apply_custom_extractions(tree, html_str, data, custom_extractors)
        if custom_searches:
            self._apply_custom_searches(html_str, data, custom_searches)

        return data

    # ------------------------------------------------------------------
    # Charset detection + decoding
    # ------------------------------------------------------------------

    def _decode_html(self, raw: bytes, content_type: str | None) -> str:
        """Decode HTML bytes to string using charset from headers or meta tags."""
        charset = None

        # 1. Try Content-Type header
        if content_type:
            for part in content_type.split(";"):
                part = part.strip().lower()
                if part.startswith("charset="):
                    charset = part[8:].strip().strip('"').strip("'")
                    break

        # 2. Try <meta charset> from first 4KB
        if not charset:
            head_bytes = raw[:4096]
            try:
                head_str = head_bytes.decode("ascii", errors="ignore")
                # <meta charset="utf-8">
                m = re.search(r'<meta\s+charset=["\']?([^"\'>\s]+)', head_str, re.I)
                if m:
                    charset = m.group(1)
                # <meta http-equiv="Content-Type" content="text/html; charset=...">
                if not charset:
                    m = re.search(
                        r'<meta[^>]+content=["\'][^"\']*charset=([^"\';\s]+)',
                        head_str,
                        re.I,
                    )
                    if m:
                        charset = m.group(1)
            except Exception:
                pass

        # 3. Fallback to utf-8 with error replacement
        if not charset:
            charset = "utf-8"

        try:
            return raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Extraction methods — one per data field, following PLAN.md order
    # ------------------------------------------------------------------

    def _extract_title(self, tree: HTMLParser, data: PageData) -> None:
        """1. Extract <title> tag and count all title tags."""
        all_titles = tree.css("title")
        data.title_count = len(all_titles)
        node = all_titles[0] if all_titles else None
        if node and node.text():
            data.title = node.text().strip()
            data.title_length = len(data.title)

    def _extract_meta_description(self, tree: HTMLParser, data: PageData) -> None:
        """2. Extract <meta name="description"> and count all meta description tags."""
        all_descs = tree.css('meta[name="description"], meta[name="Description"]')
        data.meta_desc_count = len(all_descs)
        node = all_descs[0] if all_descs else None
        if node:
            content = node.attributes.get("content", "")
            if content:
                data.meta_description = content.strip()
                data.meta_desc_length = len(data.meta_description)

    def _extract_robots_meta(self, tree: HTMLParser, data: PageData) -> None:
        """3. Extract <meta name="robots"> directives."""
        robots_nodes = tree.css('meta[name="robots"], meta[name="googlebot"]')
        data.robots_meta_tag_count = len(robots_nodes)
        directives = []
        for node in robots_nodes:
            content = node.attributes.get("content", "")
            if content:
                for directive in content.lower().split(","):
                    d = directive.strip()
                    if d and d not in directives:
                        directives.append(d)
        data.robots_meta = directives

    def _extract_canonical(self, tree: HTMLParser, data: PageData, base_url: str) -> None:
        """4. Extract <link rel="canonical"> and count all canonical tags."""
        all_canonicals = tree.css('link[rel="canonical"]')
        data.canonical_count = len(all_canonicals)
        node = all_canonicals[0] if all_canonicals else None
        if node:
            href = node.attributes.get("href", "")
            if href:
                resolved = normalize_url(href.strip(), base_url)
                data.canonical_url = resolved

    def _extract_headings(self, tree: HTMLParser, data: PageData) -> None:
        """5. Extract <h1>-<h6> headings with sequence tracking."""
        for node in tree.css("h1"):
            text = node.text(strip=True)
            if text:
                data.h1.append(text)
        for node in tree.css("h2"):
            text = node.text(strip=True)
            if text:
                data.h2.append(text)
        # Build heading sequence (h1-h6 in document order) for hierarchy validation
        for node in tree.css("h1, h2, h3, h4, h5, h6"):
            tag = node.tag
            if tag and tag.lower() in ("h1", "h2", "h3", "h4", "h5", "h6"):
                data.heading_sequence.append(tag.lower())

    def _extract_links(
        self,
        tree: HTMLParser,
        data: PageData,
        base_url: str,
        base_domain: str,
    ) -> None:
        """6. Extract all <a href> links with classification."""
        for node in tree.css("a[href]"):
            href = node.attributes.get("href", "")
            if not href:
                continue

            resolved = normalize_url(href, base_url)
            if not resolved:
                continue

            # Anchor text
            anchor = node.text(strip=True) or ""

            # Rel attributes
            rel_str = node.attributes.get("rel", "")
            rel_attrs = [r.strip().lower() for r in rel_str.split() if r.strip()] if rel_str else []

            # Classify link type
            link_domain = extract_domain(resolved)
            if link_domain == base_domain or link_domain.endswith(f".{base_domain}"):
                link_type = "internal"
            else:
                link_type = "external"

            data.links.append(
                LinkData(
                    url=resolved,
                    anchor_text=anchor[:500],  # Cap anchor text
                    rel_attrs=rel_attrs,
                    link_type=link_type,
                    tag="a",
                )
            )

        # Resource links: <link rel="stylesheet">, <script src>, <iframe src>
        for node in tree.css("link[rel='stylesheet'][href]"):
            href = node.attributes.get("href", "")
            resolved = normalize_url(href, base_url)
            if resolved:
                data.links.append(
                    LinkData(
                        url=resolved,
                        anchor_text="",
                        rel_attrs=[],
                        link_type="resource",
                        tag="link",
                    )
                )

        for node in tree.css("script[src]"):
            src = node.attributes.get("src", "")
            resolved = normalize_url(src, base_url)
            if resolved:
                data.links.append(
                    LinkData(
                        url=resolved,
                        anchor_text="",
                        rel_attrs=[],
                        link_type="resource",
                        tag="script",
                    )
                )

        for node in tree.css("iframe[src]"):
            src = node.attributes.get("src", "")
            resolved = normalize_url(src, base_url)
            if resolved:
                data.links.append(
                    LinkData(
                        url=resolved,
                        anchor_text="",
                        rel_attrs=[],
                        link_type="resource",
                        tag="iframe",
                    )
                )

    def _extract_images(self, tree: HTMLParser, data: PageData, base_url: str) -> None:
        """7. Extract <img> tags with src, srcset, alt, dimensions."""
        for node in tree.css("img"):
            src = node.attributes.get("src", "") or node.attributes.get("data-src", "")
            if not src:
                continue
            resolved = normalize_url(src, base_url)
            if not resolved:
                continue

            data.images.append(
                ImageData(
                    src=resolved,
                    alt=node.attributes.get("alt", "") or "",
                    srcset=node.attributes.get("srcset"),
                    width=node.attributes.get("width"),
                    height=node.attributes.get("height"),
                )
            )

    def _extract_hreflang(self, tree: HTMLParser, data: PageData, base_url: str) -> None:
        """8. Extract <link rel="alternate" hreflang="...">."""
        for node in tree.css('link[rel="alternate"][hreflang]'):
            hreflang = node.attributes.get("hreflang", "")
            href = node.attributes.get("href", "")
            if hreflang and href:
                resolved = normalize_url(href.strip(), base_url)
                if resolved:
                    data.hreflang_tags.append(HreflangData(hreflang=hreflang, href=resolved))

    def _extract_pagination(self, tree: HTMLParser, data: PageData, base_url: str) -> None:
        """Extract <link rel="next"> and <link rel="prev"> pagination attributes."""
        next_nodes = tree.css('link[rel="next"]')
        prev_nodes = tree.css('link[rel="prev"]')

        next_count = len(next_nodes)
        prev_count = len(prev_nodes)

        if next_count == 0 and prev_count == 0:
            return

        rel_next = None
        rel_prev = None

        if next_nodes:
            href = next_nodes[0].attributes.get("href", "")
            if href:
                rel_next = normalize_url(href.strip(), base_url)

        if prev_nodes:
            href = prev_nodes[0].attributes.get("href", "")
            if href:
                rel_prev = normalize_url(href.strip(), base_url)

        data.pagination = PaginationData(rel_next=rel_next, rel_prev=rel_prev)
        data.pagination_count = {"next": next_count, "prev": prev_count}

    def _extract_structured_data(
        self, tree: HTMLParser, data: PageData, base_url: str = ""
    ) -> None:
        """9. Extract <script type="application/ld+json"> blocks."""
        for node in tree.css('script[type="application/ld+json"]'):
            raw_text = node.text(strip=True)
            if not raw_text:
                continue
            try:
                parsed = json.loads(raw_text)
                data.structured_data_blocks.append(parsed)
            except (json.JSONDecodeError, ValueError):
                logger.debug("invalid_json_ld_block", url=base_url)

    def _extract_og_tags(self, tree: HTMLParser, data: PageData) -> None:
        """10. Extract <meta property="og:*"> Open Graph tags."""
        og = {}
        for node in tree.css('meta[property^="og:"]'):
            prop = node.attributes.get("property", "")
            content = node.attributes.get("content", "")
            if prop and content:
                # e.g. "og:title" → "title"
                key = prop[3:]  # strip "og:" prefix
                og[key] = content
        data.og_tags = og

    # ------------------------------------------------------------------
    # Content metrics
    # ------------------------------------------------------------------

    def _compute_word_count(self, tree: HTMLParser, data: PageData) -> None:
        """Compute word count from visible text (excluding script/style/noscript).

        Uses selectolax's strip_tags approach: remove invisible tags first,
        then extract all remaining text.
        """
        body = tree.css_first("body")
        if body is None:
            data.word_count = 0
            return

        # Remove invisible elements from a copy of the tree
        # selectolax doesn't have decompose, so we use text() with deep=True
        # after stripping the unwanted tags
        for tag_name in _INVISIBLE_TAGS:
            for node in body.css(tag_name):
                node.decompose()

        # Get all remaining visible text
        full_text = body.text(separator=" ", strip=True)
        full_text = _WS_RE.sub(" ", full_text).strip()
        data.word_count = len(full_text.split()) if full_text else 0

        # Content analysis: text-to-code ratio and readability
        if full_text and data.word_count > 0:
            html_len = len(tree.html or "")
            text_len = len(full_text)
            data.text_ratio = round(text_len / max(html_len, 1), 4)

            # Flesch Reading Ease (English approximation, works reasonably for other languages)
            if data.word_count >= 30:
                sentences = _count_sentences(full_text)
                syllables = _count_syllables(full_text)
                if sentences > 0:
                    data.avg_words_per_sentence = round(data.word_count / sentences, 1)
                    # Flesch formula: 206.835 - 1.015*(words/sentences) - 84.6*(syllables/words)
                    asl = data.word_count / sentences
                    asw = syllables / max(data.word_count, 1)
                    data.readability_score = round(206.835 - 1.015 * asl - 84.6 * asw, 1)
                    # Clamp to 0-100
                    data.readability_score = max(0.0, min(100.0, data.readability_score))

        # Compute SimHash for near-duplicate detection (skip very short pages)
        if full_text and data.word_count >= 50:
            from app.analysis.simhash import simhash

            data.simhash = simhash(full_text)

    def _compute_content_hash(self, html_str: str, data: PageData) -> None:
        """MD5 hash of normalized HTML for exact-duplicate detection."""
        # Normalize: collapse whitespace, lowercase for more robust dedup
        normalized = _WS_RE.sub(" ", html_str).strip().lower()
        data.content_hash = hashlib.md5(normalized.encode("utf-8")).digest()

    # ------------------------------------------------------------------
    # Mixed content detection
    # ------------------------------------------------------------------

    def _detect_mixed_content(self, tree: HTMLParser, data: PageData, base_url: str) -> None:
        """Detect HTTP resources loaded on an HTTPS page (mixed content)."""
        if not base_url.startswith("https://"):
            return

        mixed = []
        # Check img src, script src, link href (stylesheets), iframe src
        for selector, attr in [
            ("img[src]", "src"),
            ("script[src]", "src"),
            ('link[rel="stylesheet"][href]', "href"),
            ("iframe[src]", "src"),
        ]:
            for node in tree.css(selector):
                val = node.attributes.get(attr, "")
                if val and val.startswith("http://"):
                    mixed.append(val)

        # Check img srcset for mixed content (responsive images)
        for node in tree.css("img[srcset]"):
            srcset = node.attributes.get("srcset", "")
            for entry in srcset.split(","):
                src = entry.strip().split()[0] if entry.strip() else ""
                if src.startswith("http://"):
                    mixed.append(src)

        data.mixed_content_urls = mixed[:50]  # Cap at 50 to avoid bloating seo_data

    # ------------------------------------------------------------------
    # Custom extraction rules (Phase 3E)
    # ------------------------------------------------------------------

    def _apply_custom_extractions(
        self,
        tree: HTMLParser,
        html_str: str,
        data: PageData,
        rules: list[dict],
    ) -> None:
        for rule in rules:
            name = rule.get("name", "")
            method = rule.get("method", "css")
            selector = rule.get("selector", "")
            extract_type = rule.get("extract_type", "text")
            attribute_name = rule.get("attribute_name", "")
            extractor_id = str(rule.get("id", ""))

            if not name or not selector:
                continue

            try:
                if method == "xpath":
                    result = self._extract_xpath(html_str, selector, extract_type, attribute_name)
                elif method == "regex":
                    result = self._extract_regex(html_str, selector)
                else:
                    result = self._extract_css(tree, selector, extract_type, attribute_name)
                
                # Store full dict so inserter can join by extractor_id
                data.custom_extractions[extractor_id] = result
            except Exception as exc:
                logger.debug(
                    "custom_extraction_failed",
                    rule_name=name,
                    selector=selector,
                    error=str(exc),
                )
                data.custom_extractions[extractor_id] = None

    def _extract_regex(self, html_str: str, pattern: str) -> str | None:
        """Extract using standard Python regex."""
        try:
            match = re.search(pattern, html_str)
            if match:
                # If there are capture groups return the first one, else full match
                return match.group(1) if match.lastindex else match.group(0)
            return None
        except re.error:
            return None

    def _apply_custom_searches(
        self,
        html_str: str,
        data: PageData,
        searches: list[dict],
    ) -> None:
        for search in searches:
            search_id = str(search.get("id", ""))
            pattern = search.get("pattern", "")
            is_regex = search.get("is_regex", False)
            case_sensitive = search.get("case_sensitive", False)
            contains = search.get("contains", True)

            if not pattern:
                continue

            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                if is_regex:
                    matches = re.findall(pattern, html_str, flags=flags)
                    found_count = len(matches)
                else:
                    # Literal string search
                    target = html_str if case_sensitive else html_str.lower()
                    query = pattern if case_sensitive else pattern.lower()
                    found_count = target.count(query)

                # Store result
                data.custom_search_results[search_id] = found_count
            except Exception as exc:
                logger.debug(
                    "custom_search_failed",
                    search_id=search_id,
                    pattern=pattern,
                    error=str(exc),
                )
                data.custom_search_results[search_id] = 0

    def _extract_css(
        self,
        tree: HTMLParser,
        selector: str,
        extract_type: str,
        attribute_name: str,
    ) -> str | int | None:
        nodes = tree.css(selector)
        if extract_type == "count":
            return len(nodes)
        if not nodes:
            return None
        node = nodes[0]
        if extract_type == "attribute" and attribute_name:
            return node.attributes.get(attribute_name)
        if extract_type == "html":
            return node.html
        # default: text
        return node.text(strip=True)

    def _extract_xpath(
        self,
        html_str: str,
        selector: str,
        extract_type: str,
        attribute_name: str,
    ) -> str | int | None:
        from lxml import etree

        doc = etree.HTML(html_str)
        if doc is None:
            return None
        results = doc.xpath(selector)
        if extract_type == "count":
            return len(results) if isinstance(results, list) else (1 if results else 0)
        if not results:
            return None
        el = results[0] if isinstance(results, list) else results
        if isinstance(el, str):
            return el
        if extract_type == "attribute" and attribute_name:
            return el.get(attribute_name) if hasattr(el, "get") else None
        if extract_type == "html":
            return etree.tostring(el, encoding="unicode", method="html")
        # default: text
        return (
            etree.tostring(el, method="text", encoding="unicode").strip()
            if hasattr(el, "tag")
            else str(el)
        )

    # ------------------------------------------------------------------
    # Indexability
    # ------------------------------------------------------------------

    def _determine_indexability(self, data: PageData) -> None:
        """Determine indexability from robots meta directives."""
        if "noindex" in data.robots_meta:
            data.is_indexable = False
            data.indexability_reason = "noindex"
        elif "none" in data.robots_meta:
            # "none" is equivalent to "noindex, nofollow"
            data.is_indexable = False
            data.indexability_reason = "none"
        else:
            data.is_indexable = True
            data.indexability_reason = None
