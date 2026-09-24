"""Same-origin web crawler: discovers URLs, forms and parameters up to a
configured depth/page budget."""
from __future__ import annotations

import asyncio
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .http_client import make_client


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


async def crawl(base_url: str, max_pages: int = 30, depth: int = 2,
                cookies: dict | None = None, headers: dict | None = None,
                log=print) -> dict:
    visited: set[str] = set()
    urls: set[str] = set()
    forms: list[dict] = []
    params_urls: set[str] = set()
    queue: list[tuple[str, int]] = [(base_url, 0)]

    async with make_client(base_url=base_url, cookies=cookies, headers=headers) as client:
        while queue and len(visited) < max_pages:
            url, d = queue.pop(0)
            norm = url.split("#")[0]
            if norm in visited or d > depth:
                continue
            visited.add(norm)
            try:
                r = await client.get(norm)
            except Exception as e:
                log(f"[!] gagal fetch {norm}: {e}")
                continue
            ctype = r.headers.get("content-type", "")
            log(f"[>] ({len(visited)}/{max_pages}) {r.status_code} {norm}")
            if "text/html" not in ctype:
                continue
            html = r.text
            soup = BeautifulSoup(html, "lxml")
            urls.add(norm)
            if urlparse(norm).query:
                params_urls.add(norm)

            for a in soup.find_all("a", href=True):
                link = urljoin(norm, a["href"]).split("#")[0]
                if link.startswith(("mailto:", "javascript:", "tel:")):
                    continue
                if _same_origin(base_url, link) and link not in visited:
                    queue.append((link, d + 1))

            for form in soup.find_all("form"):
                inputs = []
                for inp in form.find_all(["input", "textarea", "select"]):
                    inputs.append({
                        "name": inp.get("name"),
                        "type": inp.get("type", inp.name),
                        "value": inp.get("value"),
                        "required": inp.has_attr("required"),
                    })
                forms.append({
                    "page": norm,
                    "action": urljoin(norm, form.get("action", norm)),
                    "method": (form.get("method") or "get").lower(),
                    "inputs": inputs,
                })

    return {
        "base_url": base_url,
        "pages_visited": sorted(visited),
        "pages_count": len(visited),
        "forms": forms,
        "urls_with_params": sorted(params_urls),
    }
