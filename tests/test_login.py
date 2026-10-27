import base64
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import filter as app


def make_token(exp_timestamp):
    claims = {"exp": int(exp_timestamp), "sub": "test"}
    payload = base64.urlsafe_b64encode(
        json.dumps(claims).encode("utf-8")).decode("ascii").rstrip("=")
    return f"header.{payload}.signature"


def cookie_file(token):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([{
            "name": "pku_token",
            "value": token,
            "domain": "",
            "path": "/",
            "expires": None,
            "secure": False,
            "rest": {},
        }], handle)
    return path


class LoginTests(unittest.TestCase):
    def test_placeholder_config_detection(self):
        self.assertTrue(app.is_placeholder_config("你的学号", "你的密码"))
        self.assertTrue(app.is_placeholder_config("2300012345", "你的密码"))
        self.assertFalse(app.is_placeholder_config("2300012345", "secret"))

    def test_oauth_error_text_prefers_nested_errors(self):
        self.assertEqual(
            app.oauth_error_text({"success": False, "errors": {
                "code": "E01", "msg": "User ID or Password is NOT correct."}}),
            "User ID or Password is NOT correct.（E01）")
        self.assertEqual(app.oauth_error_text({"success": False, "message": "需要验证"}),
                         "需要验证")
        self.assertEqual(app.oauth_error_text({}), "未知错误")

    def test_sso_login_parses_query_and_fragment(self):
        for url, expected in (
            ("https://treehole.pku.edu.cn/web/?token=abc123&plat=web", "abc123"),
            ("https://treehole.pku.edu.cn/ch/web/#/iaaa_success?token=def456&x=1", "def456"),
        ):
            with self.subTest(url=url):
                client = app.TreeholeClientSimple.__new__(app.TreeholeClientSimple)
                client.session = app.requests.Session()
                response = Mock()
                response.url = url
                response.raise_for_status = Mock()
                client.session.get = Mock(return_value=response)
                self.assertTrue(client.sso_login("token"))
                self.assertEqual(client.session.headers["authorization"], f"Bearer {expected}")
                self.assertTrue(any(c.name == "pku_token" and c.value == expected
                                    for c in client.session.cookies))

    def test_sso_login_fails_without_token(self):
        client = app.TreeholeClientSimple.__new__(app.TreeholeClientSimple)
        client.session = app.requests.Session()
        response = Mock()
        response.url = "https://treehole.pku.edu.cn/web/error?message=x"
        response.raise_for_status = Mock()
        client.session.get = Mock(return_value=response)
        self.assertFalse(client.sso_login("token"))

    def test_saved_token_restores_authorization_and_logs_in(self):
        token = make_token(time.time() + 3600)
        path = cookie_file(token)
        self.addCleanup(os.unlink, path)
        client = app.TreeholeClientSimple(cookies_file=path)
        self.assertEqual(client.session.headers["authorization"], f"Bearer {token}")
        client.un_read = Mock(return_value=Mock(
            status_code=200, json=Mock(return_value={"success": True})))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(client.try_saved_login())
        self.assertIn("已使用本地保存的登录令牌", output.getvalue())

    def test_expired_saved_token_skips_network(self):
        token = make_token(time.time() - 60)
        path = cookie_file(token)
        self.addCleanup(os.unlink, path)
        client = app.TreeholeClientSimple(cookies_file=path)
        client.un_read = Mock()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(client.try_saved_login())
        client.un_read.assert_not_called()
        self.assertIn("过期", output.getvalue())
        self.assertNotIn("authorization", client.session.headers)

    def test_invalid_saved_token_is_cleared(self):
        token = make_token(time.time() + 3600)
        path = cookie_file(token)
        self.addCleanup(os.unlink, path)
        client = app.TreeholeClientSimple(cookies_file=path)
        client.un_read = Mock(return_value=Mock(
            status_code=401, json=Mock(side_effect=ValueError)))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(client.try_saved_login())
        self.assertNotIn("authorization", client.session.headers)

    def test_oauth_failure_prints_iaaa_message(self):
        client = app.TreeholeClientSimple.__new__(app.TreeholeClientSimple)
        client.session = app.requests.Session()
        client.oauth_login = Mock(return_value={
            "success": False,
            "errors": {"code": "E01", "msg": "User ID or Password is NOT correct."}})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertFalse(client.ensure_login("2300012345", "wrong", interactive=False))
        self.assertIn("User ID or Password is NOT correct.", output.getvalue())
        self.assertIn("账号或密码错误", output.getvalue())

    def test_login_without_sso_token_is_reported(self):
        client = app.TreeholeClientSimple.__new__(app.TreeholeClientSimple)
        client.session = app.requests.Session()
        client.oauth_login = Mock(return_value={"success": True, "token": "abc"})
        client.sso_login = Mock(return_value=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertFalse(client.ensure_login("2300012345", "secret", interactive=False))
        self.assertIn("SSO 登录失败", output.getvalue())


if __name__ == "__main__":
    unittest.main()
