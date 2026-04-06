
"""
树洞帖子评论数筛选工具 (独立版)
功能：根据关键词搜索树洞帖子，筛选出评论数大于指定值的帖子，输出洞号。
使用：双击运行，按提示输入学号、密码、关键词、最小评论数。
注意：需要连接北大 VPN 或在校内网络环境下使用。
"""

import os
import sys
import json
import re
import uuid
import random
from http.cookiejar import Cookie
import requests

# ==================== 树洞 API 客户端（精简内嵌版）====================
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

    def search_posts(self, keyword, page=1, limit=50, comment_limit=0):
        url = "https://treehole.pku.edu.cn/chapi/api/v3/hole/list_comments"
        params = {
            "page": page,
            "limit": limit,
            "comment_limit": comment_limit,
            "keyword": keyword
        }
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

# ==================== 主程序 ====================
def main():
    print("=" * 50)
    print("树洞帖子评论数筛选工具")
    print("=" * 50)
    print("注意：请确保已连接北大 VPN 或在校内网络环境下运行。\n")

    username = input("请输入学号: ").strip()
    if not username:
        print("学号不能为空")
        input("按回车键退出...")
        return

    password = input("请输入密码: ").strip()
    if not password:
        print("密码不能为空")
        input("按回车键退出...")
        return

    keyword = input("请输入搜索关键词 (如: popi, 选课, 课程): ").strip()
    if not keyword:
        print("关键词不能为空")
        input("按回车键退出...")
        return

    try:
        min_comments = int(input("请输入最小评论数 (如: 100): ").strip())
    except ValueError:
        print("最小评论数必须是整数")
        input("按回车键退出...")
        return

    # 创建客户端并登录
    client = TreeholeClientSimple()
    print("\n正在登录树洞，可能需要几秒钟...")
    if not client.ensure_login(username, password, interactive=True):
        print("登录失败，请检查学号密码，并确认网络正常（需要VPN/校内网）。")
        input("按回车键退出...")
        return

    # 翻页搜索
    MAX_PAGES = input("请输入最大搜索页数 (默认 15): ").strip()
    if not MAX_PAGES:
        MAX_PAGES = 15
    else:
        MAX_PAGES = int(MAX_PAGES)
    LIMIT = 50
    all_posts = []
    page = 1
    print(f"\n开始搜索关键词「{keyword}」，最多 {MAX_PAGES} 页...")
    while page <= MAX_PAGES:
        print(f"正在获取第 {page} 页...")
        result = client.search_posts(keyword, page=page, limit=LIMIT, comment_limit=0)
        if not result.get("success"):
            print(f"搜索失败: {result.get('message')}")
            break
        posts = result["data"]["data"]
        if not posts:
            print("没有更多帖子了。")
            break
        all_posts.extend(posts)
        print(f"本页 {len(posts)} 个帖子，累计 {len(all_posts)} 个")
        # 检查是否最后一页
        total = result["data"].get("total", 0)
        if page * LIMIT >= total:
            print("已到达最后一页。")
            break
        page += 1

    print(f"\n总共获取 {len(all_posts)} 个帖子。")

    # 筛选
    filtered = [p for p in all_posts if p.get("comment_total", 0) > min_comments]
    print(f"评论数 > {min_comments} 的帖子共有 {len(filtered)} 个：")
    if filtered:
        for p in filtered:
            pid = p.get("pid")
            comment_total = p.get("comment_total", 0)
            print(f"洞号: {pid} (评论数: {comment_total})")
    else:
        print("未找到符合条件的帖子。")

    print("\n完成。")
    input("按回车键退出...")

if __name__ == "__main__":
    main()