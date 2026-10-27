import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import filter as app


def response(names, last=1, total=None, code=False):
    data = {"data": [{"name": n} for n in names], "last_page": last}
    if total is not None:
        data["total"] = total
    return {("code" if code else "success"): (20000 if code else True), "data": data}


class UniqueTests(unittest.TestCase):
    def count(self, pages, **kwargs):
        client = Mock()
        client.get_comments.side_effect = pages
        with patch.object(app.time, "sleep"):
            result = app.count_unique_commenters(client, 123, **kwargs)
        return result, client

    def test_cross_page_names_and_lz(self):
        result, client = self.count([
            response(["Alice", "Alice", "洞主"], 2, 5),
            response(["Bob", "Alice"], 2, 5),
        ])
        self.assertEqual(result, (3, None))
        self.assertEqual([c.kwargs["page"] for c in client.get_comments.call_args_list], [1, 2])

    def test_empty_and_code_response(self):
        self.assertEqual(self.count([response([], total=0, code=True)])[0], (0, None))

    def test_incomplete_responses_are_unknown(self):
        cases = [
            [response([None])], [response([""])], [response(["Anonymous"])],
            [{"success": False}], [{"success": True, "data": {"data": []}}],
            [response(["Alice"], total=2)],
            [response(["Alice"], 2), response(["Alice"], 2)],
            [response(["Alice"], 2), response([], 2)],
            [response(["Alice"], 2), response(["Bob"], 3)],
            [response(["Alice"], 2), app.requests.Timeout("test")],
            [{"success": True, "data": {"data": [42], "last_page": 1}}],
        ]
        for pages in cases:
            with self.subTest(pages=pages):
                result, _ = self.count(pages)
                self.assertIsNone(result[0])
                self.assertTrue(result[1])

    def test_page_limit_and_overlap(self):
        self.assertIsNone(self.count([response(["Alice"], 2)], max_pages=1)[0][0])
        first = response(["Alice"], 2)
        second = response(["Bob"], 2)
        first["data"]["data"][0]["cid"] = 1
        second["data"]["data"][0]["cid"] = 1
        self.assertIsNone(self.count([first, second])[0][0])

    def test_menu_filters_and_isolates_posts(self):
        client = Mock()
        client.search_posts.return_value = {"success": True, "data": {"total": 2, "data": [
            {"pid": 1}, {"pid": 2}]}}
        client.get_comments.side_effect = [response(["Alice", "Bob"]), response(["Alice"])]
        output = io.StringIO()
        with patch.object(app, "choose_filter_conditions", return_value=[("独立评论人数", "unique_commenters", 1)]), patch("builtins.input", side_effect=["", "", "1", ""]), contextlib.redirect_stdout(output):
            app.keyword_filter_mode(client)
        self.assertIn("洞号: 1 (独立评论人数: 2)", output.getvalue())
        self.assertNotIn("洞号: 2 (", output.getvalue())

    def test_failure_overwrites_existing_count(self):
        client = Mock()
        client.search_posts.return_value = {"success": True, "data": {"total": 1, "data": [
            {"pid": 1, "unique_commenters": 999}]}}
        client.get_comments.return_value = {"success": False}
        output = io.StringIO()
        with patch.object(app, "choose_filter_conditions", return_value=[("独立评论人数", "unique_commenters", 1)]), patch("builtins.input", side_effect=["", "", "1", ""]), contextlib.redirect_stdout(output):
            app.keyword_filter_mode(client)
        self.assertIn("无法执行此项筛选", output.getvalue())
        self.assertNotIn("999", output.getvalue())

    def test_legacy_name_tag_remains_supported(self):
        page = response(["Alice"])
        page["data"]["data"] = [{"name_tag": "Alice"}, {"name_tag": "Alice"}, {"name_tag": "Bob"}]
        self.assertEqual(self.count([page])[0], (2, None))

    def test_live_shape_name_field_counts_lz_and_duplicates(self):
        # 脱敏结构取自实际响应，不保存评论正文。
        page = response(["Alice", "Alice", "Bob", "Carol", "洞主"], total=5, code=True)
        self.assertEqual(self.count([page])[0], (4, None))

    def test_empty_object_requires_confirmed_zero_reply(self):
        for reply, expected in ((0, 0), (1, None), (None, None)):
            with self.subTest(reply=reply):
                client = Mock()
                client.get_comments.return_value = {"code": 20000, "success": True, "data": {}}
                client.get_post.return_value = {"code": 20000, "data": {"reply": reply}}
                count, error = app.count_unique_commenters(client, 123)
                self.assertEqual(count, expected)
                self.assertEqual(error is None, expected == 0)
                client.get_post.assert_called_once_with(123)

    def test_empty_object_detail_failure_is_unknown(self):
        client = Mock()
        client.get_comments.return_value = {"success": True, "data": {}}
        client.get_post.side_effect = app.requests.Timeout("offline")
        count, error = app.count_unique_commenters(client, 123)
        self.assertIsNone(count)
        self.assertTrue(error)

    def test_name_preferred_over_name_tag(self):
        page = response(["Alice", "Bob"])
        for comment in page["data"]["data"]:
            comment["name_tag"] = "Anonymous"
        self.assertEqual(self.count([page])[0], (2, None))

    def test_transport(self):
        client = app.TreeholeClientSimple.__new__(app.TreeholeClientSimple)
        client.session = Mock()
        client.session.get.return_value.json.return_value = response(["Alice"])
        client.get_comments(123, page=2)
        client.session.get.assert_called_once_with(
            "https://treehole.pku.edu.cn/api/pku_comment_v3/123",
            params={"page": 2, "limit": 100, "sort": "asc"}, timeout=30)
        with self.assertRaises(ValueError):
            client.get_comments("../bad")
