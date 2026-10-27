应一位同学的需求，整了一个树洞帖子筛评论的小工具，然后顺手整了个日榜。

使用方法：

1.在config.json配置好用户名、密码。

2.安装依赖 `python -m pip install -r requirements.txt`，运行 `python filter.py`，选择功能 1，输入关键词（留空为无关键词）、筛选指标和阈值，再输入起始页码和搜索页数。程序输出已抓取页范围内，**总评论数、收藏数或独立评论人数严格大于阈值**的洞号。指标留空默认总评论数；阈值必须为非负整数，页码和页数必须为正整数。

如果有人看到（）如果有什么别的需求欢迎提出来，我看看能不能加进去。

注：

对于树洞API的使用，借鉴了 https://github.com/SunVapor/pku-treehole-search-agent 项目中的代码，原作者声明使用 MIT License，感谢SunVapor的开源贡献。

筛选说明：

- 总评论数使用搜索响应的 `comment_total`，收藏数使用 `likenum`；不额外请求旧接口，不改变搜索及分页语义。
- 字段接受非负整数或整数字符串。缺失、null 或非法值会被跳过并提示；全部不可用时明确报告无法筛选，不将未知值当作 0。
- 选择指标 3 可试用独立评论人数筛选：逐帖请求 `/api/pku_comment_v3/{pid}`，按同一帖子全部评论的 `name_tag` 去重。包含实际发表评论的洞主，不计未回复的发帖者；只统计接口当前可见评论，不推测删除或隐藏评论的作者。不同帖子的同名昵称分别统计。
- 该统计采用“同帖匿名昵称对应固定评论者”的口径，不根据最大字母推算人数。当前服务端字段及昵称稳定性尚需真实账号验证。
- 必须读完 `last_page` 指定的所有评论页；若有 `total`，还要核对条数。缺少分页元数据、昵称缺失、重复页、分页变化、条数不符、超时或超过 1000 页上限时，该帖明确标为不可用并跳过，不把部分统计当作准确人数。抓取期间内容变化仍可能影响结果。
- 评论接口及分页依据：[上游 client.py](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/client.py) 和 [agent.py](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/agent.py)；昵称字段依据：[utils.py](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/utils.py)。
- 收藏字段依据：[上游客户端 search_posts 响应示例](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/client.py)。尚未使用真实账号验证当前服务端响应。
- 今日热榜保持原行为。源码改动不会更新已有 `dist/filter.exe`；需要使用 `pyinstaller filter.spec` 重新打包。

离线验证：`python -m unittest discover -s tests -v`。测试使用模拟响应，无需账号或校内网络。

手工试用：连接校内网或 VPN，运行 `python filter.py`，功能 1 → 指标 3，先仅搜索 1 页；挑一个帖子对照全部评论昵称的去重数（包括有回复的洞主）。遇到未知响应结构会提示跳过，请先核验响应再扩展兼容。
