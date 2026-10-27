"""
树洞工具集 (增强版)
功能1：根据关键词搜索树洞帖子，按总评论数、收藏数或独立评论人数筛选，输出洞号。
功能2：查看今日热榜（24小时内，按收藏数×1.2+回复数×1.8排序）
使用：双击运行，按提示选择功能、输入学号密码等。
注意：需要连接北大 VPN 或在校内网络环境下使用。
"""

import os
import sys
import json
import re
import uuid
import random
from datetime import datetime, timedelta
import time
from http.cookiejar import Cookie
import requests

#读信息#

def load_config(config_file="config.json"):
    """从同目录的 config.json 读取用户名和密码，返回 (username, password) 或 (None, None)"""
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    if not os.path.exists(config_path):
        return None, None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        username = config.get("username")
        password = config.get("password")
        if username and password:
            return username, password
        else:
            print("配置文件缺少 username 或 password 字段。")
            return None, None
    except Exception as e:
        print(f"读取配置文件出错: {e}")
        return None, None


# ==================== 树洞 API 客户端（增强版）====================
class TreeholeClientSimple:
    def __init__(self, cookies_file=None):
        self.session = requests.Session()
        if cookies_file is None:
            cookies_file = os.path.expanduser("~/.treehole_cookies.json")
        self.cookies_file = cookies_file
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        # 禁用代理（解决 SSL 错误）
        self.session.trust_env = False
        self.session.proxies = {}
        self.load_cookies()

    def load_cookies(self):
        try:
            with open(self.cookies_file, 'r') as f:
                cookies_list = json.load(f)
            self.session.cookies.clear()
            for cookie_dict in cookies_list:
                cookie = Cookie(
                    version=0,
                    name=cookie_dict["name"],
                    value=cookie_dict["value"],
                    port=None,
                    port_specified=False,
                    domain=cookie_dict["domain"],
                    domain_specified=bool(cookie_dict["domain"]),
                    domain_initial_dot=cookie_dict["domain"].startswith('.'),
                    path=cookie_dict["path"],
                    path_specified=bool(cookie_dict["path"]),
                    secure=cookie_dict["secure"],
                    expires=cookie_dict.get("expires"),
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest=cookie_dict.get("rest", {})
                )
                self.session.cookies.set_cookie(cookie)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"加载 cookies 出错: {e}")

    def save_cookies(self):
        cookies_list = []
        for cookie in self.session.cookies:
            cookie_dict = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "expires": cookie.expires if cookie.expires else None,
                "secure": cookie.secure,
                "rest": {"HttpOnly": cookie.has_nonstandard_attr("HttpOnly")}
            }
            cookies_list.append(cookie_dict)
        try:
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies_list, f, indent=4)
        except Exception as e:
            print(f"保存 cookies 出错: {e}")

    def oauth_login(self, username, password):
        url = "https://iaaa.pku.edu.cn/iaaa/oauthlogin.do"
        data = {
            "appid": "PKU Helper",
            "userName": username,
            "password": password,
            "randCode": "",
            "smsCode": "",
            "otpCode": "",
            "redirUrl": "https://treehole.pku.edu.cn/cas_iaaa_login?uuid=fc71db5799cf&plat=web"
        }
        resp = self.session.post(url, data=data)
        resp.raise_for_status()
        return resp.json()

    def sso_login(self, token):
        url = "http://treehole.pku.edu.cn/cas_iaaa_login"
        params = {
            "uuid": str(uuid.uuid4()).split("-")[-1],
            "plat": "web",
            "_rand": str(random.random()),
            "token": token
        }
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        # 从重定向 URL 中提取 token
        match = re.search(r"token=(.*)", resp.url)
        if match:
            auth_token = match.group(1)
            self.session.cookies.update({"pku_token": auth_token})
            self.session.headers.update({"authorization": f"Bearer {auth_token}"})
            return True
        return False

    def un_read(self):
        resp = self.session.get("https://treehole.pku.edu.cn/api/mail/un_read")
        return resp

    def send_message(self):
        resp = self.session.post("https://treehole.pku.edu.cn/api/jwt_send_msg")
        return resp

    def login_by_message(self, code):
        resp = self.session.post("https://treehole.pku.edu.cn/api/jwt_msg_verify", data={"valid_code": code})
        return resp

    def login_by_token(self, token):
        resp = self.session.post("https://treehole.pku.edu.cn/api/login_iaaa_check_token", data={"code": token})
        return resp

    def ensure_login(self, username, password, interactive=True):
        # 检查是否已登录
        try:
            resp = self.un_read()
            if resp.status_code == 200 and resp.json().get("success"):
                return True
        except:
            pass

        # 未登录，执行 OAuth 登录
        print("正在登录...")
        try:
            result = self.oauth_login(username, password)
            if result.get("success") == "true" or result.get("success") is True:
                token = result.get("token")
                if token and self.sso_login(token):
                    # 二次验证
                    max_attempts = 5
                    attempt = 0
                    while attempt < max_attempts:
                        attempt += 1
                        resp = self.un_read()
                        if resp.status_code == 200 and resp.json().get("success"):
                            self.save_cookies()
                            return True
                        msg = resp.json().get("message", "")
                        if "手机短信" in msg:
                            if not interactive:
                                print("需要短信验证，但当前为非交互模式，登录失败。")
                                return False
                            print("需要短信验证码。")
                            self.send_message()
                            code = input("请输入短信验证码: ").strip()
                            self.login_by_message(code)
                        elif "令牌" in msg:
                            if not interactive:
                                print("需要手机令牌验证，但当前为非交互模式，登录失败。")
                                return False
                            print("需要手机令牌（PKU Helper 动态码）。")
                            token_code = input("请输入6位动态令牌: ").strip()
                            self.login_by_token(token_code)
                        else:
                            print(f"未知验证要求: {msg}")
                            return False
                    return False
                else:
                    print("SSO 登录失败")
                    return False
            else:
                print(f"登录失败: {result.get('msg', '未知错误')}")
                return False
        except Exception as e:
            print(f"登录异常: {e}")
            return False

    # ---------- 原有方法：使用新版 API 搜索帖子（支持无关键词）----------
    def search_posts(self, keyword=None, page=1, limit=50, comment_limit=0):
        """
        搜索帖子，若 keyword 为 None 或空字符串，则获取全站帖子（无关键词）
        """
        url = "https://treehole.pku.edu.cn/chapi/api/v3/hole/list_comments"
        params = {
            "page": page,
            "limit": limit,
            "comment_limit": comment_limit,
        }
        if keyword:  # 只有非空关键词才添加
            params["keyword"] = keyword
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 20000:
            return {
                "success": True,
                "data": {
                    "data": data["data"]["list"],
                    "total": data["data"].get("total", 0)
                }
            }
        else:
            return {"success": False, "message": data.get("message", "未知错误")}

    def get_comments(self, pid, page=1, limit=100):
        """分页读取评论；不读取或保存评论者的真实身份。"""
        if not str(pid).isascii() or not str(pid).isdigit():
            raise ValueError("无效洞号")
        response = self.session.get(
            f"https://treehole.pku.edu.cn/api/pku_comment_v3/{pid}",
            params={"page": page, "limit": limit, "sort": "asc"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ---------- 新增方法：使用旧版 API 获取原始树洞列表（用于热榜）----------
    def get_hole_list(self, page=1, limit=25, keyword=None):
        """
        直接调用旧版 /api/pku_hole 接口，返回原始 JSON。
        用于热榜计算（字段包含 likenum, reply, timestamp 等）
        """
        url = "https://treehole.pku.edu.cn/api/pku_hole"
        params = {"page": page, "limit": limit}
        if keyword:
            params["keyword"] = keyword
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ==================== 辅助函数 ====================
def timestamp_to_datetime(timestamp_10):
    """10位时间戳转字符串"""
    dt_object = datetime.utcfromtimestamp(int(timestamp_10))
    return dt_object.strftime('%Y-%m-%d %H:%M:%S')

def is_within_last_24_hours(timestamp_10):
    """判断时间戳是否在最近24小时内（UTC）"""
    dt_object = datetime.utcfromtimestamp(int(timestamp_10))
    now = datetime.utcnow()
    twenty_four_hours_ago = now - timedelta(hours=24)
    return twenty_four_hours_ago <= dt_object < now

def get_daily_hot_posts(client, max_pages=75, limit=25):
    """
    获取今日热榜前十
    遍历全站帖子（无关键词），过滤24小时内，按 收藏数*1.2 + 回复数*1.8 降序
    """
    print(f"\n正在拉取全站帖子（最多 {max_pages} 页，每页 {limit} 条）...")
    page = 1
    hot_posts = []
    while page <= max_pages:
        print(f"  获取第 {page} 页...")
        try:
            resp_json = client.get_hole_list(page=page, limit=limit, keyword=None)
            if resp_json.get("code") != 20000:
                print(f"API 返回错误: {resp_json.get('message')}")
                break
            posts = resp_json.get("data", {}).get("data", [])
            if not posts:
                print("  没有更多帖子，停止拉取。")
                break

            # 处理本页帖子
            for p in posts:
                # 检查发布时间
                ts = p.get("timestamp")
                if ts and is_within_last_24_hours(ts):
                    likenum = p.get("likenum", 0)      # 收藏数
                    reply = p.get("reply", 0)          # 回复数
                    # 热度公式
                    hot_value = likenum * 1.2 + reply * 1.8
                    hot_posts.append({
                        "pid": p.get("pid"),
                        "value": hot_value,
                        "content": p.get("text", ""),
                        "likenum": likenum,
                        "reply": reply,
                        "timestamp": ts
                    })
            # 如果本页最早的帖子已经超出24小时，可以提前结束（因为API按时间倒序）
            # 简单判断：如果本页最后一条帖子的时间早于24小时前，且页码较大，可停止
            if posts and not is_within_last_24_hours(posts[-1].get("timestamp")):
                # 但后续页面可能还有更早的，不过热榜只需要24小时内，所以可以停止
                print("  已遇到24小时外的帖子，停止拉取后续页面。")
                break

            page += 1
            # 适当延迟，避免请求过快
            time.sleep(0.2)
        except Exception as e:
            print(f"  获取第 {page} 页失败: {e}")
            break

    if not hot_posts:
        print("未找到24小时内的帖子。")
        return []

    # 按热度降序排序
    hot_posts.sort(key=lambda x: x["value"], reverse=True)
    return hot_posts[:10]

# 搜索接口 likenum 字段依据：上游 SunVapor/pku-treehole-search-agent
# client.py 的 search_posts/get_comment，以及 utils.py 的 name_tag 展示。
FILTER_METRICS = {
    "1": ("总评论数", "comment_total"),
    "2": ("收藏数", "likenum"),
    "3": ("独立评论人数", "unique_commenters"),
}


def get_metric_value(post, field):
    """只接受非负整数及其字符串形式；缺失或非法值不能作为零。"""
    value = post.get(field)
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    return None


def filter_posts(posts, field, threshold):
    """返回 (符合条件的帖子, 指标不可用的帖子数)，保留严格大于语义。"""
    filtered = []
    unavailable = 0
    for post in posts:
        value = get_metric_value(post, field)
        if value is None:
            unavailable += 1
        elif value > threshold:
            filtered.append(post)
    return filtered, unavailable


def parse_filter_conditions(rows):
    """只校验勾选项，返回 (标签, 字段, 阈值) 列表。"""
    conditions = []
    for label, field, enabled, raw in rows:
        if not enabled:
            continue
        value = get_metric_value({field: raw}, field)
        if value is None:
            raise ValueError(f"{label}阈值必须是非负整数")
        conditions.append((label, field, value))
    if not conditions:
        raise ValueError("请至少勾选一个筛选条件")
    return conditions


def choose_filter_conditions():
    """主菜单选择 1 后弹出复选框，多项条件按 AND 组合。"""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        print("当前 Python 未安装 Tkinter，无法打开条件选择框。")
        return None
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        print(f"无法打开条件选择框：{exc}")
        return None
    window.title("选择筛选条件")
    window.resizable(False, False)
    panel = ttk.Frame(window, padding=24)
    panel.grid()
    ttk.Label(panel, text="勾选要使用的筛选条件", font=("Microsoft YaHei UI", 13, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
    ttk.Label(panel, text="多选时须同时满足；每项均严格大于右侧阈值。").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))
    rows = []
    for index, (label, field) in enumerate(FILTER_METRICS.values(), 2):
        enabled = tk.BooleanVar(value=False)
        value = tk.StringVar(value="0")
        entry = ttk.Entry(panel, textvariable=value, width=12, state="disabled")
        def toggle(flag=enabled, widget=entry):
            widget.configure(state="normal" if flag.get() else "disabled")
        ttk.Checkbutton(panel, text=label, variable=enabled, command=toggle).grid(
            row=index, column=0, sticky="w", pady=8)
        ttk.Label(panel, text=">").grid(row=index, column=1, padx=16)
        entry.grid(row=index, column=2, sticky="e")
        rows.append((label, field, enabled, value))
    ttk.Label(panel, text="独立评论人数需额外读取评论，可能耗时较长。").grid(
        row=5, column=0, columnspan=3, sticky="w", pady=(12, 4))
    error = tk.StringVar()
    ttk.Label(panel, textvariable=error, foreground="#b42318").grid(
        row=6, column=0, columnspan=3, sticky="w", pady=8)
    result = None
    def confirm():
        nonlocal result
        try:
            result = parse_filter_conditions([
                (label, field, enabled.get(), value.get())
                for label, field, enabled, value in rows])
        except ValueError as exc:
            error.set(str(exc))
            return
        window.destroy()
    buttons = ttk.Frame(panel)
    buttons.grid(row=7, column=0, columnspan=3, sticky="e")
    ttk.Button(buttons, text="取消", command=window.destroy).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="确定", command=confirm).pack(side="left")
    window.bind("<Return>", lambda event: confirm())
    window.bind("<Escape>", lambda event: window.destroy())
    window.attributes("-topmost", True)
    window.after(250, lambda: window.attributes("-topmost", False))
    window.mainloop()
    return result


def filter_posts_by_conditions(client, posts, conditions):
    """AND 筛选；先检查已返回指标，只对剩余候选读取评论。"""
    matches, issues = [], []
    counts = {}
    cheap = [(label, field, threshold) for label, field, threshold in conditions
             if field != "unique_commenters"]
    unique = next((condition for condition in conditions
                   if condition[1] == "unique_commenters"), None)
    for original in posts:
        post = dict(original)
        values = [(label, get_metric_value(post, field), threshold)
                  for label, field, threshold in cheap]
        if any(value is not None and value <= threshold for _, value, threshold in values):
            continue
        missing = [label for label, value, _ in values if value is None]
        if missing:
            issues.append((post.get("pid"), "、".join(missing) + "缺失或无效"))
            continue
        if unique:
            label, field, threshold = unique
            pid = post.get("pid")
            key = str(pid)
            if key not in counts:
                counts[key] = count_unique_commenters(client, pid)
            count, error = counts[key]
            if error:
                issues.append((pid, error))
                continue
            post[field] = count
            if count <= threshold:
                continue
        matches.append(post)
    return matches, issues


def count_unique_commenters(client, pid, max_pages=1000):
    """按单帖 name_tag 去重，包含实际回复的洞主；失败时返回未知及原因。

    分页结构来自上游 agent._fetch_all_comments_for_post。必须有分页元数据，
    不将搜索命中的 comment_total 当作该帖完整评论总数。
    """
    names = set()
    seen_pages = set()
    seen_ids = set()
    received = 0
    expected_last = expected_total = None
    for page in range(1, max_pages + 1):
        try:
            response = client.get_comments(pid, page=page, limit=100)
            if not isinstance(response, dict) or not (
                response.get("success") is True or response.get("code") == 20000
            ):
                return None, "评论接口返回失败"
            data = response.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                return None, "无法识别评论响应结构"
            comments = data["data"]
            last = get_metric_value(data, "last_page")
            total = get_metric_value(data, "total")
            if page == 1:
                expected_last, expected_total = last, total
                if last is None or last < 1:
                    return None, "缺少有效 last_page，无法确认评论是否完整"
                if last > max_pages:
                    return None, "评论页数超过上限，未完成统计"
            elif last != expected_last or total != expected_total:
                return None, "抓取期间分页信息变化，未完成统计"
            if not comments and (page < expected_last or expected_last > 1):
                return None, "评论分页提前为空，未完成统计"
            if comments:
                fingerprint = json.dumps(comments, sort_keys=True, ensure_ascii=False)
                if fingerprint in seen_pages:
                    return None, "评论接口返回重复页，未完成统计"
                seen_pages.add(fingerprint)
            for comment in comments:
                if not isinstance(comment, dict):
                    return None, "评论记录格式无效"
                name = comment.get("name_tag")
                if not isinstance(name, str) or not name.strip() or name.strip().lower() == "anonymous":
                    return None, "评论匿名昵称缺失，无法准确去重"
                # cid 若存在，用于发现分页重叠；不猜测其他身份字段。
                cid = comment.get("cid")
                if cid is not None:
                    key = str(cid)
                    if key in seen_ids:
                        return None, "评论分页重叠，未完成统计"
                    seen_ids.add(key)
                names.add(name.strip())
            received += len(comments)
            if page == expected_last:
                if expected_total is not None and received != expected_total:
                    return None, "评论条数与接口总数不一致，未完成统计"
                return len(names), None
            time.sleep(0.2)
        except (requests.RequestException, ValueError, TypeError) as exc:
            return None, f"评论读取失败：{exc}"
    return None, "评论页数超过上限，未完成统计"


# ==================== 关键词筛选功能 ====================
def keyword_filter_mode(client):
    """按勾选条件联合筛选；支持无关键词。"""
    print("\n" + "=" * 50)
    print("关键词筛选模式")
    print("=" * 50)
    conditions = choose_filter_conditions()
    if not conditions:
        print("已取消筛选，返回主菜单。")
        return
    description = " 且 ".join(f"{label} > {threshold}" for label, _, threshold in conditions)
    print(f"已选择：{description}")
    keyword = input("请输入搜索关键词（直接回车表示无关键词，即全站搜索）: ").strip()
    # 如果 keyword 为空字符串，后续 search_posts 会不传 keyword 参数，实现无关键词查找
    if keyword == "":
        keyword = None
        print("已切换到无关键词模式，将获取全站帖子。")

    try:
        start_page_input = input("请输入起始页码 (默认 1): ").strip()
        start_page = int(start_page_input) if start_page_input else 1
        page_count_input = input("请输入要爬取的页数 (默认 15): ").strip()
        page_count = int(page_count_input) if page_count_input else 15
        if start_page < 1 or page_count < 1:
            raise ValueError
    except ValueError:
        print("起始页码和页数必须是正整数")
        return
    end_page = start_page + page_count - 1

    LIMIT = 50
    all_posts = []
    page = start_page
    print(f"\n开始搜索，从第 {start_page} 页到第 {end_page} 页...")
    while page <= end_page:
        print(f"正在获取第 {page} 页...")
        try:
            result = client.search_posts(keyword=keyword, page=page, limit=LIMIT, comment_limit=0)
        except (requests.RequestException, ValueError) as exc:
            print(f"获取第 {page} 页失败: {exc}；以下仅为已获取范围的结果。")
            break
        if not result.get("success"):
            print(f"搜索失败: {result.get('message')}；以下仅为已获取范围的结果。")
            break
        posts = result["data"]["data"]
        if not posts:
            print(f"第 {page} 页没有帖子，可能已到末尾。停止抓取。")
            break
        all_posts.extend(posts)
        print(f"本页 {len(posts)} 个帖子，累计 {len(all_posts)} 个")
        # 检查是否已到达最后一页（如果总帖子数已知且当前页已超过）
        total = result["data"].get("total", 0)
        if total > 0 and page * LIMIT >= total:
            print("已到达最后一页。")
            break
        page += 1
        time.sleep(0.2)

    print(f"\n总共获取 {len(all_posts)} 个帖子。")
    if any(field == "unique_commenters" for _, field, _ in conditions):
        print("正在按勾选条件筛选；仅对满足其他条件的帖子读取评论...")
    filtered, issues = filter_posts_by_conditions(client, all_posts, conditions)
    for pid, reason in issues:
        print(f"洞号 {pid}：{reason}，已跳过。")
    if issues:
        print(f"警告：{len(issues)} 个帖子的勾选指标无法确认，结果可能不完整。")
    if all_posts and len(issues) == len(all_posts):
        print("当前响应不提供可用的勾选指标，无法执行此项筛选。")
    else:
        print(f"已获取范围内，满足 {description} 的帖子共有 {len(filtered)} 个：")
        if filtered:
            for post in filtered:
                details = "，".join(f"{label}: {get_metric_value(post, field)}"
                                    for label, field, _ in conditions)
                print(f"洞号: {post.get('pid')} ({details})")
        else:
            print("未找到符合条件的帖子。")
    input("\n按回车键返回主菜单...")

# ==================== 今日热榜功能 ====================
def hot_trend_mode(client):
    """今日热榜模式"""
    print("\n" + "=" * 50)
    print("今日热榜模式（24小时内，热度=收藏×1.2+回复×1.8）")
    print("=" * 50)
    hot_list = get_daily_hot_posts(client, max_pages=75, limit=25)
    if not hot_list:
        print("未找到足够的热门帖子。")
    else:
        print("\n【今日树洞热榜前十】")
        for idx, post in enumerate(hot_list, start=1):
            print(f"\n第 {idx} 名：树洞号 {post['pid']}，热度 {post['value']:.1f} "
                  f"(收藏 {post['likenum']}，回复 {post['reply']})")
            # 截取内容前200字符避免过长
            content_preview = post['content'][:200] + "..." if len(post['content']) > 200 else post['content']
            print(f"内容：{content_preview}")
    input("\n按回车键返回主菜单...")

# ==================== 主程序 ====================
def main():
    print("=" * 50)
    print("树洞工具集 (增强版)")
    print("=" * 50)
    print("注意：请确保已连接北大 VPN 或在校内网络环境下运行。\n")

    # 登录
    cfg_user, cfg_pass = load_config()
    if cfg_user and cfg_pass:
        use_cfg = input(f"检测到配置文件中的账号：{cfg_user}，是否使用？(y/n，默认 y): ").strip().lower()
        if use_cfg != 'n':
            username, password = cfg_user, cfg_pass
        else:
            username = input("请输入学号: ").strip()
            password = input("请输入密码: ").strip()
    else:
        username = input("请输入学号: ").strip()
        password = input("请输入密码: ").strip()

    if not username or not password:
        print("学号或密码不能为空")
        input("按回车键退出...")
        return

    client = TreeholeClientSimple()
    print("\n正在登录树洞，可能需要几秒钟...")
    if not client.ensure_login(username, password, interactive=True):
        print("登录失败，请检查学号密码，并确认网络正常（需要VPN/校内网）。")
        input("按回车键退出...")
        return
    print("登录成功！\n")

    # 功能选择循环
    while True:
        print("\n请选择功能：")
        print("1. 条件筛选（勾选总评论数、收藏数、独立评论人数）")
        print("2. 今日热榜（无关键词，按热度排序）")
        print("0. 退出")
        choice = input("请输入数字: ").strip()
        if choice == "1":
            keyword_filter_mode(client)
        elif choice == "2":
            hot_trend_mode(client)
        elif choice == "0":
            print("感谢使用，再见！")
            break
        else:
            print("无效输入，请重新选择。")

if __name__ == "__main__":
    main()