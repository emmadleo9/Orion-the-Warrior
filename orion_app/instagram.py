from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class InstagramError(RuntimeError):
    pass


@dataclass
class InstagramToken:
    access_token: str
    user_id: str
    expires_at: float
    granted_scopes: tuple[str, ...]


class InstagramIntegration:
    AUTH_URL = "https://www.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    GRAPH_URL = "https://graph.instagram.com"
    SCOPES = (
        "instagram_business_basic",
        "instagram_business_content_publish",
        "instagram_business_manage_messages",
        "instagram_business_manage_comments",
    )

    def __init__(self) -> None:
        self.app_id = os.getenv("ORION_INSTAGRAM_APP_ID", "").strip()
        self.app_secret = os.getenv("ORION_INSTAGRAM_APP_SECRET", "").strip()
        self.redirect_uri = os.getenv(
            "ORION_INSTAGRAM_REDIRECT_URI",
            "http://localhost:8000/api/instagram/callback",
        ).strip()
        self.api_version = os.getenv("ORION_INSTAGRAM_API_VERSION", "v25.0").strip()
        parsed_redirect = urlparse(self.redirect_uri)
        if parsed_redirect.scheme not in {"http", "https"} or not parsed_redirect.netloc:
            raise ValueError("ORION_INSTAGRAM_REDIRECT_URI must be an absolute HTTP(S) URL.")
        if not self.api_version.startswith("v") or not self.api_version[1:].replace(".", "").isdigit():
            raise ValueError("ORION_INSTAGRAM_API_VERSION must use a version such as v25.0.")
        self._pending_states: dict[str, float] = {}
        self._token: InstagramToken | None = None
        self._lock = threading.RLock()

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    def status(self) -> dict:
        with self._lock:
            token = self._token
            connected = token is not None and token.expires_at > time.time()
            if token is not None and not connected:
                self._token = None
                token = None
            user_id = token.user_id if connected and token else None
        return {
            "configured": self.configured,
            "connected": connected,
            "user_id": user_id,
            "scopes": list(token.granted_scopes) if connected and token else [],
            "api_version": self.api_version,
            "token_storage": "in-memory for this Orion process",
            "account_requirement": "Instagram professional account (Business or Creator)",
        }

    def authorization_url(self) -> str:
        if not self.configured:
            raise InstagramError("Set ORION_INSTAGRAM_APP_ID and ORION_INSTAGRAM_APP_SECRET first.")
        state = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._pending_states = {
                key: expires_at for key, expires_at in self._pending_states.items()
                if expires_at > now
            }
            self._pending_states[state] = now + 600
        return f"{self.AUTH_URL}?{urlencode({
            'client_id': self.app_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ','.join(self.SCOPES),
            'state': state,
            'enable_fb_login': '0',
            'force_authentication': '1',
        })}"

    def complete_authorization(self, code: str, state: str) -> None:
        now = time.time()
        with self._lock:
            expiry = self._pending_states.pop(state, None)
        if not state or expiry is None or expiry <= now:
            raise InstagramError("Instagram authorization state was missing, expired, or already used.")
        if not code:
            raise InstagramError("Instagram did not return an authorization code.")

        short_token = self._request(
            self.TOKEN_URL,
            method="POST",
            form={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        access_token = short_token.get("access_token")
        user_id = short_token.get("user_id")
        if not isinstance(access_token, str) or not access_token or not user_id:
            raise InstagramError("Instagram returned an incomplete authorization response.")

        long_token = self._request(
            f"{self.GRAPH_URL}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self.app_secret,
                "access_token": access_token,
            },
        )
        long_access_token = long_token.get("access_token")
        if not isinstance(long_access_token, str) or not long_access_token:
            raise InstagramError("Instagram did not issue a long-lived access token.")
        permissions = short_token.get("permissions", [])
        granted_scopes = (
            tuple(scope for scope in permissions if isinstance(scope, str))
            if isinstance(permissions, list)
            else ()
        )
        expires_in = long_token.get("expires_in", 60 * 24 * 60 * 60)
        try:
            lifetime = max(0, int(expires_in))
        except (TypeError, ValueError) as error:
            raise InstagramError("Instagram returned an invalid token lifetime.") from error
        with self._lock:
            self._token = InstagramToken(
                long_access_token,
                str(user_id),
                now + lifetime,
                granted_scopes,
            )

    def disconnect(self) -> None:
        with self._lock:
            self._token = None
            self._pending_states.clear()

    def refresh(self) -> dict:
        token = self._require_token()
        result = self._request(
            f"{self.GRAPH_URL}/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": token.access_token,
            },
        )
        access_token = result.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise InstagramError("Instagram did not return a refreshed access token.")
        try:
            lifetime = int(result["expires_in"])
        except (KeyError, TypeError, ValueError) as error:
            raise InstagramError("Instagram returned an invalid token lifetime.") from error
        with self._lock:
            self._token = InstagramToken(
                access_token,
                token.user_id,
                time.time() + lifetime,
                token.granted_scopes,
            )
        return self.status()

    def profile(self) -> dict:
        return self._api("me", params={"fields": "user_id,username,account_type,media_count"})

    def media(self, limit: int = 20) -> dict:
        return self._api(
            "me/media",
            params={
                "fields": "id,caption,media_type,media_url,permalink,timestamp,comments_count,like_count",
                "limit": str(max(1, min(limit, 50))),
            },
        )

    def insights(self, period: str = "day") -> dict:
        if period not in {"day", "week", "days_28", "month", "lifetime"}:
            raise InstagramError("Unsupported Instagram insights period.")
        return self._api(
            "me/insights",
            params={
                "metric": "reach,profile_views,total_interactions",
                "period": period,
            },
        )

    def comments(self, media_id: str) -> dict:
        return self._api(
            f"{self._validate_id(media_id)}/comments",
            params={"fields": "id,text,username,timestamp"},
        )

    def reply_to_comment(self, comment_id: str, message: str) -> dict:
        cleaned = message.strip()
        if not cleaned or len(cleaned) > 2000:
            raise InstagramError("Comment replies must contain 1 to 2000 characters.")
        return self._api(
            f"{self._validate_id(comment_id)}/replies",
            method="POST",
            form={"message": cleaned},
        )

    def conversations(self) -> dict:
        return self._api(
            "me/conversations",
            params={"platform": "instagram", "fields": "id,updated_time"},
        )

    def conversation_messages(self, conversation_id: str) -> dict:
        return self._api(
            self._validate_id(conversation_id),
            params={"fields": "messages{id,created_time,from,to,message}"},
        )

    def send_message(self, recipient_id: str, message: str) -> dict:
        cleaned = message.strip()
        if not cleaned or len(cleaned) > 1000:
            raise InstagramError("Instagram messages must contain 1 to 1000 characters.")
        return self._api(
            f"{self._require_token().user_id}/messages",
            method="POST",
            form={
                "recipient": json.dumps({"id": self._validate_id(recipient_id)}),
                "message": json.dumps({"text": cleaned}),
            },
        )

    def publish_image(self, image_url: str, caption: str = "") -> dict:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise InstagramError("Instagram publishing needs a publicly reachable HTTPS image URL.")
        if len(caption) > 2200:
            raise InstagramError("Instagram captions cannot exceed 2200 characters.")
        token = self._require_token()
        container = self._api(
            f"{token.user_id}/media",
            method="POST",
            form={"image_url": image_url, "caption": caption},
        )
        creation_id = container.get("id")
        if not isinstance(creation_id, str) or not creation_id:
            raise InstagramError("Instagram did not create a media publishing container.")
        deadline = time.monotonic() + 30
        while True:
            status = self._api(creation_id, params={"fields": "status_code"})
            status_code = status.get("status_code")
            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                raise InstagramError("Instagram could not process the image for publishing.")
            if status_code != "IN_PROGRESS":
                raise InstagramError("Instagram returned an unknown media processing status.")
            if time.monotonic() >= deadline:
                raise InstagramError("Instagram image processing timed out; try publishing again.")
            time.sleep(1)
        return self._api(
            f"{token.user_id}/media_publish",
            method="POST",
            form={"creation_id": creation_id},
        )

    def _require_token(self) -> InstagramToken:
        with self._lock:
            token = self._token
            if token is None or token.expires_at <= time.time():
                self._token = None
                raise InstagramError("Connect your Instagram professional account first.")
            return token

    @staticmethod
    def _validate_id(value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-." for char in cleaned):
            raise InstagramError("Instagram returned an invalid identifier.")
        return cleaned

    def _api(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        method: str = "GET",
        form: dict[str, str] | None = None,
    ) -> dict:
        token = self._require_token()
        request_params = dict(params or {})
        if method == "GET":
            request_params["access_token"] = token.access_token
        else:
            form = dict(form or {})
            form["access_token"] = token.access_token
        url = f"{self.GRAPH_URL}/{self.api_version}/{path}"
        if request_params:
            url += "?" + urlencode(request_params)
        return self._request(url, method=method, form=form)

    @staticmethod
    def _request(
        url: str,
        *,
        method: str = "GET",
        params: dict[str, str] | None = None,
        form: dict[str, str] | None = None,
    ) -> dict:
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)
        body = urlencode(form).encode("utf-8") if form is not None else None
        request = Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "OrionTheWarrior/0.1",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                detail = json.loads(error.read().decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                detail = {}
            api_error = detail.get("error", {}) if isinstance(detail, dict) else {}
            message = api_error.get("message") if isinstance(api_error, dict) else None
            raise InstagramError(message or f"Instagram returned HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise InstagramError("Could not reach Instagram. Check your connection and try again.") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InstagramError("Instagram returned an invalid response.") from error
        if not isinstance(result, dict):
            raise InstagramError("Instagram returned an invalid response.")
        if "error" in result:
            error = result["error"]
            message = error.get("message") if isinstance(error, dict) else None
            raise InstagramError(message or "Instagram rejected the request.")
        return result
