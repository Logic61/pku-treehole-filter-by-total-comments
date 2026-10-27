import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import filter as app


class FilterTests(unittest.TestCase):
    def run_mode(self, inputs, pages):
        client = Mock()
        client.search_posts.side_effect = pages
        output = io.StringIO()
        with patch("builtins.input", side_effect=inputs), patch.object(app.time, "sleep"), contextlib.redirect_stdout(output):
            app.keyword_filter_mode(client)
        return client, output.getvalue()

    def test_threshold_and_invalid_values(self):
        values = [0, 99, 100, 101, " 102 ", None, -1, True, 1.5, "bad", "1.0"]
        posts = [{"pid": i, "likenum": v} for i, v in enumerate(values)] + [{"pid": 99}]
        matches, unavailable = app.filter_posts(posts, "likenum", 100)
        self.assertEqual([p["pid"] for p in matches], [3, 4])
        self.assertEqual(unavailable, 7)
        self.assertEqual(app.get_metric_value({"likenum": "0"}, "likenum"), 0)

    def test_default_comments_and_total_pagination(self):
        page = {"success": True, "data": {"data": [{"pid": 7, "comment_total": 101}], "total": 1}}
        client, text = self.run_mode(["", "", "100", "", "", ""], [page])
        client.search_posts.assert_called_once_with(keyword=None, page=1, limit=50, comment_limit=0)
        self.assertIn("洞号: 7 (总评论数: 101)", text)

    def test_favorites_keyword_and_page_range(self):
        page = {"success": True, "data": {"data": [{"pid": 8, "likenum": "3"}, {"pid": 9}], "total": 0}}
        client, text = self.run_mode(["test", "2", "2", "3", "2", ""], [page, {"success": True, "data": {"data": [], "total": 0}}])
        self.assertEqual([c.kwargs["page"] for c in client.search_posts.call_args_list], [3, 4])
        self.assertEqual(client.search_posts.call_args.kwargs["keyword"], "test")
        self.assertIn("洞号: 8 (收藏数: 3)", text)
        self.assertIn("1 个帖子的收藏数缺失或无效", text)

    def test_all_unavailable_is_not_no_matches(self):
        page = {"success": True, "data": {"data": [{"pid": 1}], "total": 1}}
        _, text = self.run_mode(["", "2", "0", "", "", ""], [page])
        self.assertIn("无法执行此项筛选", text)
        self.assertNotIn("未找到符合条件", text)

    def test_invalid_inputs_do_not_request(self):
        for inputs in (["", "9"], ["", "2", "-1"], ["", "1", "x"], ["", "1", "0", "x", "1"], ["", "1", "0", "1", "0"]):
            with self.subTest(inputs=inputs):
                client, _ = self.run_mode(inputs, [])
                client.search_posts.assert_not_called()

    def test_failure_reports_partial_results(self):
        page = {"success": True, "data": {"data": [{"pid": 1, "likenum": 2}], "total": 0}}
        for error in ({"success": False, "message": "denied"}, app.requests.ConnectionError("offline")):
            with self.subTest(error=error):
                _, text = self.run_mode(["", "2", "0", "1", "2", ""], [page, error])
                self.assertIn("已获取范围", text)
                self.assertIn("洞号: 1 (收藏数: 2)", text)

    def test_search_adapter_preserves_fields_and_omits_empty_keyword(self):
        client = app.TreeholeClientSimple.__new__(app.TreeholeClientSimple)
        client.session = Mock()
        post = {"pid": 1, "likenum": 3, "comment_total": 4}
        client.session.get.return_value.json.return_value = {"code": 20000, "data": {"list": [post], "total": 1}}
        self.assertEqual(client.search_posts()["data"]["data"], [post])
        self.assertNotIn("keyword", client.session.get.call_args.kwargs["params"])

    def test_hot_trend_ranking_unchanged(self):
        client = Mock()
        client.get_hole_list.return_value = {"code": 20000, "data": {"data": [
            {"pid": 1, "timestamp": 1, "likenum": 2, "reply": 1},
            {"pid": 2, "timestamp": 1, "likenum": 1, "reply": 3}]}}
        with patch.object(app, "is_within_last_24_hours", return_value=True), patch.object(app.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual([p["pid"] for p in app.get_daily_hot_posts(client, max_pages=1)], [2, 1])


if __name__ == "__main__":
    unittest.main()
