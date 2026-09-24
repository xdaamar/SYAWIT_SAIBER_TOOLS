"""Web API routes: crawler, form analyzer, OWASP scan, SQLMap, auth bypass."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.job_manager import jobs, launch_async_job, launch_process_job
from ..modules.web import auth_bypass, form_analyzer, owasp_checks
from ..modules.web import sqlmap_runner
from ..modules.web.crawler import crawl

router = APIRouter(prefix="/api/web", tags=["web"])


class CrawlBody(BaseModel):
    url: str
    max_pages: int = 30
    depth: int = 2
    cookies: dict = {}
    headers: dict = {}


@router.post("/crawl")
async def crawl_route(body: CrawlBody):
    """Fast enough to run inline (page-budget bounded)."""
    result = await crawl(body.url, max_pages=min(body.max_pages, 200),
                         depth=min(body.depth, 5), cookies=body.cookies or None,
                         headers=body.headers or None)
    result["analysis"] = form_analyzer.analyze_forms(
        result["forms"], result["urls_with_params"])
    return result


class AnalyzeBody(BaseModel):
    forms: list[dict] = []
    urls_with_params: list[str] = []


@router.post("/forms/analyze")
def analyze_forms(body: AnalyzeBody):
    return form_analyzer.analyze_forms(body.forms, body.urls_with_params)


class OwaspBody(BaseModel):
    url: str
    params_urls: list[str] = []
    forms: list[dict] = []
    cookies: dict = {}
    headers: dict = {}


@router.post("/owasp")
async def owasp(body: OwaspBody):
    job = launch_async_job(
        jobs, "web", f"OWASP scan {body.url}", f"owasp-scan {body.url}",
        lambda append: owasp_checks.run_owasp_scan(
            body.url, params_urls=body.params_urls, forms=body.forms,
            cookies=body.cookies or None, headers=body.headers or None,
            log=append),
    )
    return {"job": job.to_dict()}


class SqlmapBody(BaseModel):
    url: str
    data: str = ""
    level: int = 1
    risk: int = 1
    forms: bool = False
    dump: bool = False
    cookie: str = ""
    extra: str = ""


@router.post("/sqlmap/preview")
def sqlmap_preview(body: SqlmapBody):
    cmd = sqlmap_runner.build_command(
        body.url, data=body.data, level=body.level, risk=body.risk,
        forms=body.forms, dump=body.dump, cookie=body.cookie, extra=body.extra)
    if not cmd:
        raise HTTPException(409, "sqlmap belum terinstall — jalankan Setup dulu")
    return {"command": " ".join(str(c) for c in cmd), "argv": cmd}


@router.post("/sqlmap/run")
def sqlmap_run(body: SqlmapBody):
    cmd = sqlmap_runner.build_command(
        body.url, data=body.data, level=body.level, risk=body.risk,
        forms=body.forms, dump=body.dump, cookie=body.cookie, extra=body.extra)
    if not cmd:
        raise HTTPException(409, "sqlmap belum terinstall — jalankan Setup dulu")

    def build_result(job, rc, lines):
        return sqlmap_runner.parse_summary(lines)

    job = launch_process_job(
        jobs, "web", f"sqlmap {body.url}", cmd, build_result=build_result)
    return {"job": job.to_dict()}


class AuthBypassBody(BaseModel):
    url: str
    username_field: str = "username"
    password_field: str = "password"
    extra_fields: dict = {}
    cookies: dict = {}
    headers: dict = {}
    delay: float = 0.2


@router.post("/auth-bypass")
async def auth_bypass_route(body: AuthBypassBody):
    job = launch_async_job(
        jobs, "web", f"Auth bypass {body.url}", f"auth-bypass {body.url}",
        lambda append: auth_bypass.test_login_bypass(
            body.url, username_field=body.username_field,
            password_field=body.password_field,
            extra_fields=body.extra_fields or None,
            cookies=body.cookies or None, headers=body.headers or None,
            delay=body.delay, log=append),
    )
    return {"job": job.to_dict()}


class JwtBody(BaseModel):
    token: str


@router.post("/jwt")
def jwt(body: JwtBody):
    return auth_bypass.analyze_jwt(body.token)


class CookieTamperBody(BaseModel):
    base_url: str
    cookie_name: str
    values: list[str]
    check_url: str | None = None
    headers: dict = {}


@router.post("/cookie-tamper")
async def cookie_tamper(body: CookieTamperBody):
    job = launch_async_job(
        jobs, "web", f"Cookie tamper {body.cookie_name}",
        f"cookie-tamper {body.base_url} ({body.cookie_name})",
        lambda append: auth_bypass.test_cookie_tamper(
            body.base_url, body.cookie_name, body.values,
            check_url=body.check_url, headers=body.headers or None, log=append),
    )
    return {"job": job.to_dict()}
