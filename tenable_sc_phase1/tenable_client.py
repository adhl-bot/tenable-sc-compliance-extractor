from __future__ import annotations

import http.cookiejar
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import TenableConfig


class TenableAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_code: int | str | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.body = body


@dataclass(frozen=True)
class AnalysisResponse:
    total_records: int
    returned_records: int
    results: list[dict[str, Any]]
    raw: dict[str, Any]


class TenableSCClient:
    def __init__(self, config: TenableConfig) -> None:
        self.config = config
        self.base_url = config.url.rstrip("/")
        self.token: str | None = None
        self._headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "holcim-tenable-sc-phase1/0.1",
        }
        self._cookie_jar = http.cookiejar.CookieJar()
        handlers: list[urllib.request.BaseHandler] = [
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        ]
        if self.base_url.lower().startswith("https://"):
            context = ssl.create_default_context()
            if not config.verify_ssl:
                context = ssl._create_unverified_context()
            handlers.append(urllib.request.HTTPSHandler(context=context))
        self._opener = urllib.request.build_opener(*handlers)

    def __enter__(self) -> "TenableSCClient":
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.logout()

    def login(self) -> None:
        if self.config.auth_mode == "api_keys":
            if not self.config.access_key or not self.config.secret_key:
                raise TenableAPIError("Missing Tenable.sc API keys in configuration")
            self._headers["X-APIKey"] = (
                f"accessKey={self.config.access_key}; secretKey={self.config.secret_key}"
            )
            return

        if not self.config.username or not self.config.password:
            raise TenableAPIError("Missing Tenable.sc username/password in configuration")

        data = self.request(
            "POST",
            "token",
            json_body={
                "username": self.config.username,
                "password": self.config.password,
            },
            authenticated=False,
        )
        token = data.get("response", {}).get("token")
        if token is None:
            raise TenableAPIError("Tenable.sc login did not return a token", body=data)
        self.token = str(token)
        self._headers["X-SecurityCenter"] = self.token

    def logout(self) -> None:
        if self.config.auth_mode != "session" or not self.token:
            return
        try:
            self.request("DELETE", "token")
        except TenableAPIError:
            pass
        finally:
            self.token = None
            self._headers.pop("X-SecurityCenter", None)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        url = self._url(path, params)
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = dict(self._headers)
        if not authenticated:
            headers.pop("X-SecurityCenter", None)
            headers.pop("X-APIKey", None)

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.config.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except urllib.error.URLError as exc:
            raise TenableAPIError(f"Tenable.sc connection error: {exc}") from exc

        error_code = payload.get("error_code")
        if error_code not in (None, 0, "0"):
            raise TenableAPIError(
                payload.get("error_msg") or "Tenable.sc API returned an error",
                error_code=error_code,
                body=payload,
            )
        return payload

    def list_assets(self) -> list[dict[str, Any]]:
        data = self.request(
            "GET",
            "asset",
            params={
                "fields": "id,name,type,description,tags,ipCount,groups,canUse,uuid"
            },
        )
        return data.get("response", {}).get("usable", [])

    def get_asset(self, asset_id: int | str) -> dict[str, Any]:
        data = self.request("GET", f"asset/{asset_id}")
        return data.get("response", {})

    def list_audit_files(self) -> list[dict[str, Any]]:
        data = self.request(
            "GET",
            "auditFile",
            params={
                "fields": "id,name,filename,description,type,groups,createdTime,modifiedTime,uuid"
            },
        )
        return data.get("response", {}).get("usable", [])

    def compliance_details(
        self,
        *,
        filters: list[dict[str, Any]],
        start_offset: int = 0,
        end_offset: int = 200,
        tool: str = "vulndetails",
    ) -> AnalysisResponse:
        payload = {
            "type": "vuln",
            "sourceType": "cumulative",
            "query": {
                "type": "vuln",
                "tool": tool,
                "startOffset": start_offset,
                "endOffset": end_offset,
                "filters": filters,
            },
        }
        data = self.request("POST", "analysis", json_body=payload)
        response = data.get("response", {})
        return AnalysisResponse(
            total_records=int(response.get("totalRecords") or 0),
            returned_records=int(response.get("returnedRecords") or 0),
            results=response.get("results") or [],
            raw=data,
        )

    def compliance_sumseverity(
        self,
        *,
        asset_id: int | str,
        audit_file_id: int | str | None = None,
    ) -> AnalysisResponse:
        filters: list[dict[str, Any]] = [
            {"filterName": "pluginType", "operator": "=", "value": "compliance"},
            {"filterName": "assetID", "operator": "=", "value": str(asset_id)},
        ]
        if audit_file_id is not None:
            filters.append(
                {
                    "filterName": "auditFileID",
                    "operator": "=",
                    "value": str(audit_file_id),
                }
            )

        payload = {
            "type": "vuln",
            "sourceType": "cumulative",
            "query": {
                "type": "vuln",
                "tool": "sumseverity",
                "startOffset": 0,
                "endOffset": 50,
                "filters": filters,
            },
        }
        data = self.request("POST", "analysis", json_body=payload)
        response = data.get("response", {})
        return AnalysisResponse(
            total_records=int(response.get("totalRecords") or 0),
            returned_records=int(response.get("returnedRecords") or 0),
            results=response.get("results") or [],
            raw=data,
        )

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        clean_path = path.strip("/")
        url = f"{self.base_url}/rest/{clean_path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return url

    def _http_error(self, exc: urllib.error.HTTPError) -> TenableAPIError:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
            message = payload.get("error_msg") or raw
            error_code = payload.get("error_code")
        except json.JSONDecodeError:
            payload = raw
            message = raw
            error_code = None
        return TenableAPIError(
            message,
            status=exc.code,
            error_code=error_code,
            body=payload,
        )
