from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class BossUrls:
    web_base: str
    acquiredp_url: str
    redfish_base: str
    redfish_root_url: str


@dataclass(frozen=True)
class ProbeResult:
    name: str
    url: str
    ok: bool
    status: int | None
    message: str


@dataclass(frozen=True)
class DiagnosticReport:
    urls: BossUrls
    probes: list[ProbeResult]

    @property
    def ok(self) -> bool:
        return all(probe.ok for probe in self.probes if probe.name in {"boss_web", "acquiredp", "redfish"})


def normalize_boss_urls(raw_boss: str) -> BossUrls:
    raw_boss = raw_boss.strip()
    if not raw_boss:
        raise ValueError("boss URL/IP is required")
    if "://" not in raw_boss:
        raw_boss = "http://" + raw_boss

    parsed = urlsplit(raw_boss)
    scheme = parsed.scheme or "http"
    host = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    if not path or path == "/":
        path = "/boss"
    if not path.lower().rstrip("/").endswith("/boss"):
        path = path.rstrip("/")
        if not path.lower().endswith("/boss"):
            path = path + "/boss"

    web_base = urlunsplit((scheme, host, path.rstrip("/"), "", ""))
    redfish_base = urlunsplit(("https", host, "", "", ""))
    return BossUrls(
        web_base=web_base,
        acquiredp_url=web_base + "/servlet/acquiredp",
        redfish_base=redfish_base,
        redfish_root_url=redfish_base + "/redfish",
    )


def _ssl_context(url: str, verify_tls: bool) -> ssl.SSLContext | None:
    if url.lower().startswith("https://") and not verify_tls:
        return ssl._create_unverified_context()
    return None


def fetch_text(url: str, *, timeout: float = 12.0, verify_tls: bool = False) -> tuple[int, str, str]:
    request = urllib.request.Request(url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context(url, verify_tls)) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, response.headers.get("Content-Type", ""), raw.decode(charset, errors="replace")


def probe_url(name: str, url: str, *, timeout: float = 12.0, verify_tls: bool = False) -> ProbeResult:
    try:
        status, content_type, body = fetch_text(url, timeout=timeout, verify_tls=verify_tls)
    except urllib.error.HTTPError as exc:
        return ProbeResult(name=name, url=url, ok=False, status=exc.code, message=f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return ProbeResult(name=name, url=url, ok=False, status=None, message=str(exc.reason))
    except TimeoutError:
        return ProbeResult(name=name, url=url, ok=False, status=None, message="timeout")

    message = content_type
    ok = 200 <= status < 300
    if name == "redfish":
        try:
            payload = json.loads(body)
            ok = ok and payload.get("v1") == "/redfish/v1/"
            message = "Redfish ativo" if ok else "Resposta Redfish inesperada"
        except json.JSONDecodeError:
            ok = False
            message = "Resposta Redfish nao e JSON"
    return ProbeResult(name=name, url=url, ok=ok, status=status, message=message)


def diagnose_boss(raw_boss: str, *, timeout: float = 12.0, verify_tls: bool = False) -> DiagnosticReport:
    urls = normalize_boss_urls(raw_boss)
    probes = [
        probe_url("boss_web", urls.web_base + "/", timeout=timeout, verify_tls=verify_tls),
        probe_url("acquiredp", urls.acquiredp_url, timeout=timeout, verify_tls=verify_tls),
        probe_url("redfish", urls.redfish_root_url, timeout=timeout, verify_tls=verify_tls),
    ]

    # A 401 here is expected without a token and proves the protected resource exists.
    protected_url = urls.redfish_base + "/redfish/v1/Chassis"
    protected = probe_url("redfish_chassis_without_token", protected_url, timeout=timeout, verify_tls=verify_tls)
    if protected.status == 401:
        protected = ProbeResult(
            name=protected.name,
            url=protected.url,
            ok=True,
            status=401,
            message="401 esperado sem token",
        )
    probes.append(protected)

    return DiagnosticReport(urls=urls, probes=probes)
