import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import filter as app


class FilterTests(unittest.TestCase):
    def run_mode(self, inputs, pages, conditions):
        client = Mock()
        client.search_posts.side_effect = pages
        output = io.StringIO()
        with patch("builtins.input", side_effect=inputs), patch.object(app, "choose_filter_conditions", return_value=conditions), patch.object(app.time, "sleep"), contextlib.redirect_stdout(output):
            app.keyword_filter_mode(client)
        return client, output.getvalue()

    def test_threshold_and_invalid_values(self):
        values = [0, 99, 100, 101, " 102 ", None, -1, True, 1.5, "bad", "1.0"]
        posts = [{"pid": i, "likenum": v} for i, v in enumerate(values)] + [{"pid": 99}]
        matches, unavailable = app.filter_posts(posts, "likenum", 100)
        self.assertEqual([p["pid"] for p in matches], [3, 4])
        self.assertEqual(unavailable, 7)

    def test_comments_and_total_pagination(self):
        page = {"success": True, "data": {"data": [{"pid": 7, "comment_total": 101}], "total": 1}}
        client, text = self.run_mode(["", "", "", ""], [page], [("总评论数", "comment_total", 100)])
        client.search_posts.assert_called_once_with(keyword=None, page=1, limit=50, comment_limit=0)
        client.get_comments.assert_not_called()
        self.assertIn("洞号: 7 (总评论数: 101)", text)

    def test_favorites_keyword_and_page_range(self):
        page = {"success": True, "data": {"data": [{"pid": 8, "likenum": "3"}, {"pid": 9}], "total": 0}}
        client, text = self.run_mode(["test", "3", "2", ""], [page, {"success": True, "data": {"data": [], "total": 0}}], [("收藏数", "likenum", 2)])
        self.assertEqual([c.kwargs["page"] for c in client.search_posts.call_args_list], [3, 4])
        self.assertEqual(client.search_posts.call_args.kwargs["keyword"], "test")
        self.assertIn("洞号: 8 (收藏数: 3)", text)
        self.assertIn("收藏数缺失或无效", text)
        self.assertNotIn("总评论数:", text)
        client.get_comments.assert_not_called()

    def test_all_unavailable_is_not_no_matches(self):
        page = {"success": True, "data": {"data": [{"pid": 1}], "total": 1}}
        _, text = self.run_mode(["", "", "", ""], [page], [("收藏数", "likenum", 0)])
        self.assertIn("无法执行此项筛选", text)
        self.assertNotIn("未找到符合条件", text)

    def test_cancel_does_not_prompt_or_request(self):
        client, text = self.run_mode([], [], None)
        client.search_posts.assert_not_called()
        self.assertIn("已取消筛选", text)

    def test_invalid_pages_do_not_request(self):
        for inputs in (["", "x", "1"], ["", "1", "0"]):
            with self.subTest(inputs=inputs):
                client, _ = self.run_mode(inputs, [], [("总评论数", "comment_total", 0)])
                client.search_posts.assert_not_called()

    def test_failure_reports_partial_results(self):
        page = {"success": True, "data": {"data": [{"pid": 1, "likenum": 2}], "total": 0}}
        for error in ({"success": False, "message": "denied"}, app.requests.ConnectionError("offline")):
            with self.subTest(error=error):
                _, text = self.run_mode(["", "1", "2", ""], [page, error], [("收藏数", "likenum", 0)])
                self.assertIn("已获取范围", text)
                self.assertIn("洞号: 1 (收藏数: 2)", text)

    def test_checkbox_validation_only_checks_enabled_rows(self):
        rows = [("总评论数", "comment_total", False, "invalid"), ("收藏数", "likenum", True, " 2 ")]
        self.assertEqual(app.parse_filter_conditions(rows), [("收藏数", "likenum", 2)])
        for rows in ([], [("收藏数", "likenum", False, "0")], [("收藏数", "likenum", True, "-1")], [("收藏数", "likenum", True, "1.5")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                app.parse_filter_conditions(rows)

    def test_combined_conditions_are_and(self):
        posts = [
            {"pid": 1, "comment_total": 11, "likenum": 6},
            {"pid": 2, "comment_total": 10, "likenum": 100},
            {"pid": 3, "comment_total": 100, "likenum": 5},
            {"pid": 4, "likenum": 6}]
        client = Mock()
        matches, issues = app.filter_posts_by_conditions(client, posts, [("总评论数", "comment_total", 10), ("收藏数", "likenum", 5)])
        self.assertEqual([p["pid"] for p in matches], [1])
        self.assertEqual([pid for pid, _ in issues], [4])
        client.get_comments.assert_not_called()

    def test_only_candidates_fetch_comments_and_repeat_pid_is_cached(self):
        posts = [{"pid": 1, "likenum": 5}, {"pid": 2, "likenum": 6}, {"pid": 2, "likenum": 6}]
        with patch.object(app, "count_unique_commenters", return_value=(3, None)) as count:
            matches, issues = app.filter_posts_by_conditions(Mock(), posts, [("收藏数", "likenum", 5), ("独立评论人数", "unique_commenters", 2)])
        self.assertEqual([p["pid"] for p in matches], [2, 2])
        self.assertFalse(issues)
        count.assert_called_once()
        self.assertEqual(count.call_args.args[1], 2)

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
