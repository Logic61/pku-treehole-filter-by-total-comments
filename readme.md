应一位同学的需求，整了一个树洞帖子筛评论的小工具，然后顺手整了个日榜。

使用方法：

1.把 config.json 里的 `username`、`password` 改成真实学号与密码。仓库自带的是「你的学号/你的密码」占位符，原样运行会登录失败（程序会给出提示）。

2.安装依赖 `python -m pip install -r requirements.txt`，运行 `python filter.py`。选择功能 1 后弹出条件窗口，勾选总评论数、收藏数、独立评论人数中的一项或多项，并分别填写阈值。多项条件须同时满足，比较均为严格大于；未勾选项不参与筛选。确定后回到终端输入关键词（留空为无关键词）、起始页码和搜索页数。结果仅显示勾选的指标。阈值必须为非负整数，页码和页数必须为正整数；取消或关闭窗口返回主菜单。

如果有人看到（）如果有什么别的需求欢迎提出来，我看看能不能加进去。

注：

对于树洞API的使用，借鉴了 https://github.com/SunVapor/pku-treehole-search-agent 项目中的代码，原作者声明使用 MIT License，感谢SunVapor的开源贡献。

筛选说明：

- 总评论数使用搜索响应的 `comment_total`，收藏数使用 `likenum`；不额外请求旧接口，不改变搜索及分页语义。
- 字段接受非负整数或整数字符串。缺失、null 或非法值会被跳过并提示；全部不可用时明确报告无法筛选，不将未知值当作 0。
- 勾选独立评论人数可试用该项筛选：逐帖请求 `/api/pku_comment_v3/{pid}`，按同一帖子全部评论的 `name` 去重（兼容 `name_tag`）。包含实际发表评论的洞主，不计未回复的发帖者；只统计接口当前可见评论，不推测删除或隐藏评论的作者。不同帖子的同名昵称分别统计。
- 该统计采用“同帖匿名昵称对应固定评论者”的口径，不根据最大字母推算人数。已用登录会话核验当前评论接口的 `name` 字段；同帖 Alice 等昵称按实际值去重。
- 必须读完 `last_page` 指定的所有评论页；若有 `total`，还要核对条数。缺少分页元数据、昵称缺失、重复页、分页变化、条数不符、超时或超过 1000 页上限时，该帖明确标为不可用并跳过，不把部分统计当作准确人数。抓取期间内容变化仍可能影响结果。
- 当前旧评论接口的无评论响应为 `data: {}`；程序额外读取帖子详情确认 `reply == 0` 才报告 0 人。空响应但回复数不为零或无法确认时仍提示跳过。
- 评论接口及分页依据：[上游 client.py](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/client.py) 和 [agent.py](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/agent.py)；昵称字段依据：[utils.py](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/utils.py)。
- 收藏字段依据：[上游客户端 search_posts 响应示例](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/client.py)。评论解析已用实际登录响应验证，测试不保存评论正文或登录凭据。
- 登录优先复用本地保存的令牌：`~/.treehole_cookies.json` 里的 `pku_token` 会恢复成 `Authorization: Bearer` 请求头，令牌未过期时不再请求 IAAA；只有缺失、失效或过期时才用账号密码登录。令牌有效期以 JWT 的 `exp` 为准（约一个月），启动时会打印到期时间。
- IAAA 登录失败时程序会显示其具体原因（账号或密码错误、短信/手机令牌验证、临时锁定等），不再统一显示“未知错误”。短信和手机令牌两种二次验证仍按提示交互输入。
- 今日热榜保持原行为。源码改动不会更新已有 `dist/filter.exe`；需要使用 `pyinstaller filter.spec` 重新打包。

离线验证：`python -m unittest discover -s tests -v`。测试使用模拟响应，无需账号或校内网络。

手工试用：连接校内网或 VPN，运行 `python filter.py`，功能 1 → 勾选独立评论人数并填写阈值 → 确定，先仅搜索 1 页；挑一个帖子对照全部评论昵称的去重数（包括有回复的洞主）。遇到未知响应结构会提示跳过，请先核验响应再扩展兼容。

条件窗口依赖 Python 自带的 Tkinter（Windows 官方 Python 安装时包含 Tcl/Tk）。默认不勾选任何项，至少选一项才能确定。未勾选独立评论人数时不会请求评论接口；勾选时先用其他条件缩小候选范围，再读取评论。
