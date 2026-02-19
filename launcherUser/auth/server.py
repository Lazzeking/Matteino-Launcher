# auth/server.py

import base64
import html
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse as urlparse
import minecraft_launcher_lib.microsoft_account as ms_account

# Launcher name for auth pages
AUTH_PAGE_TITLE = "Matteino Launcher"

# Directory containing editable templates (next to this file)
_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def _load_template(name: str, fallback: str) -> str:
    """Load template from auth/templates/ if present, else return fallback."""
    path = os.path.join(_TEMPLATES_DIR, name)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return fallback


def _logo_data_url(logo_path: str | None) -> str:
    """Return a data URL for the logo image if path exists and is readable; else empty string."""
    if not logo_path or not os.path.isfile(logo_path):
        return ""
    try:
        with open(logo_path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


def _auth_html(logo_data_url: str, title: str, message: str, is_success: bool) -> bytes:
    """Build HTML page from editable template (auth/templates/) or built-in fallback."""
    title_esc = html.escape(title)
    message_esc = html.escape(message)
    status_class = "success" if is_success else "error"
    logo_img = (
        f'<img src="{logo_data_url}" alt="Logo" class="logo" />'
        if logo_data_url
        else f'<div class="logo-placeholder">{html.escape(AUTH_PAGE_TITLE)}</div>'
    )
    success_extra = ""
    if is_success:
        success_extra = _load_template(
            "success_extra.html",
            '<div class="close-row"><p id="countdown">You can close this tab now.</p></div>',
        )
    fallback = _default_auth_page_html()
    template = _load_template("auth_page.html", fallback)
    html_body = (
        template.replace("{{PAGE_TITLE}}", html.escape(AUTH_PAGE_TITLE))
        .replace("{{LOGO_IMG}}", logo_img)
        .replace("{{STATUS_CLASS}}", status_class)
        .replace("{{TITLE}}", title_esc)
        .replace("{{MESSAGE}}", message_esc)
        .replace("{{SUCCESS_EXTRA}}", success_extra)
    )
    return html_body.encode("utf-8")


def _default_auth_page_html() -> str:
    """Built-in template used when auth_page.html is missing."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{TITLE}} - {{PAGE_TITLE}}</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: #1a1a2e; color: #e0e0e0; font-family: sans-serif; display: flex; align-items: center; justify-content: center; padding: 24px; }
    .card { background: #2e2e46; border-radius: 12px; padding: 32px; max-width: 480px; width: 100%; text-align: center; }
    .logo { max-width: 180px; max-height: 80px; margin-bottom: 24px; }
    .title { font-size: 1.25rem; font-weight: 600; margin-bottom: 12px; }
    .success .title { color: #7dd3a0; }
    .error .title { color: #e07c7c; }
    .message { font-size: 0.95rem; color: #b0b0c0; white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <div class="card {{STATUS_CLASS}}">
    {{LOGO_IMG}}
    <p class="title">{{TITLE}}</p>
    <p class="message">{{MESSAGE}}</p>
    {{SUCCESS_EXTRA}}
  </div>
</body>
</html>"""


def _complete_login_after_token(client_id, client_secret, redirect_url, code, code_verifier):
    """Do token exchange first so we can surface Microsoft's error; then finish login with the library."""
    token_request = ms_account.get_authorization_token(
        client_id, client_secret, redirect_url, code, code_verifier
    )
    if "error" in token_request:
        err = token_request.get("error", "unknown")
        desc = token_request.get(
            "error_description", token_request.get("error", ""))
        raise ValueError(f"Microsoft token error: {err} - {desc}")
    if "access_token" not in token_request:
        raise ValueError(
            "Microsoft response missing access_token (no error field). Check Azure app and redirect URI.")

    token = token_request["access_token"]
    xbl = ms_account.authenticate_with_xbl(token)
    xbl_token = xbl["Token"]
    userhash = xbl["DisplayClaims"]["xui"][0]["uhs"]

    xsts = ms_account.authenticate_with_xsts(xbl_token)
    xsts_token = xsts["Token"]

    mc = ms_account.authenticate_with_minecraft(userhash, xsts_token)
    access_token = mc["access_token"]

    profile = ms_account.get_profile(access_token)
    profile["access_token"] = access_token
    profile["refresh_token"] = token_request["refresh_token"]
    return profile


def _safe_http_message(msg: str) -> str:
    """Ensure message is encodable as Latin-1 for HTTP status line (avoids UnicodeEncodeError)."""
    return msg.encode("latin-1", "replace").decode("latin-1")


def start_temp_server(code_verifier, client_id, client_secret, redirect_url, redirect_port, logo_path=None):
    """Run a temporary HTTP server to receive the OAuth callback. Credentials come from config.
    logo_path: optional path to logo image for styled success/error pages."""
    logo_data_url = _logo_data_url(logo_path)

    def send_html_response(handler, code, title, message, is_success):
        body = _auth_html(logo_data_url, title, message, is_success)
        handler.send_response(code)
        handler.send_header("Content-type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    class AuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed_path = urlparse.urlparse(self.path)
            if parsed_path.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            query = urlparse.parse_qs(parsed_path.query)

            if "code" in query:
                code = query["code"][0]
                try:
                    self.server.login_data = _complete_login_after_token(
                        client_id, client_secret, redirect_url, code, self.server.code_verifier
                    )
                except ValueError as e:
                    send_html_response(
                        self, 400, "Login failed",
                        str(e), is_success=False
                    )
                    return
                except KeyError as e:
                    send_html_response(
                        self, 400, "Login failed",
                        f"Login response missing expected data: {e}",
                        is_success=False,
                    )
                    return
                except Exception as e:
                    send_html_response(
                        self, 500, "Server error",
                        _safe_http_message(str(e)),
                        is_success=False,
                    )
                    return

                send_html_response(
                    self, 200, "Login successful",
                    "You can close this page and return to the launcher.",
                    is_success=True,
                )
                threading.Thread(target=self.server.shutdown,
                                 daemon=True).start()
            else:
                send_html_response(
                    self, 400, "Bad request",
                    "Missing code parameter. Try logging in again from the launcher.",
                    is_success=False,
                )

    server_address = ("", redirect_port)
    httpd = HTTPServer(server_address, AuthHandler)
    httpd.code_verifier = code_verifier
    httpd.login_data = None

    while not httpd.login_data:
        httpd.handle_request()

    return httpd.login_data
