应一位同学的需求，整了一个树洞帖子筛评论的小工具，然后顺手整了个日榜。

使用方法：

1.在config.json配置好用户名、密码。

2.安装依赖 `python -m pip install -r requirements.txt`，运行 `python filter.py`，选择功能 1，输入关键词（留空为无关键词）、筛选指标和阈值，再输入起始页码和搜索页数。程序输出已抓取页范围内，**总评论数或收藏数严格大于阈值**的洞号。指标留空默认总评论数；阈值必须为非负整数，页码和页数必须为正整数。

如果有人看到（）如果有什么别的需求欢迎提出来，我看看能不能加进去。

注：

对于树洞API的使用，借鉴了 https://github.com/SunVapor/pku-treehole-search-agent 项目中的代码，原作者声明使用 MIT License，感谢SunVapor的开源贡献。

筛选说明：

- 总评论数使用搜索响应的 `comment_total`，收藏数使用 `likenum`；不额外请求旧接口，不改变搜索及分页语义。
- 字段接受非负整数或整数字符串。缺失、null 或非法值会被跳过并提示；全部不可用时明确报告无法筛选，不将未知值当作 0。
- 独立评论人数暂不可用。现有证据不足以确认汇总字段、完整评论分页和稳定匿名作者标识，不能以总评论数或部分评论估算；issue #1 尚未完整解决。
- 收藏字段依据：[上游客户端 search_posts 响应示例](https://github.com/SunVapor/pku-treehole-search-agent/blob/a4428000548c71dfb456849d564287e38a08a763/client.py)。尚未使用真实账号验证当前服务端响应。
- 今日热榜保持原行为。源码改动不会更新已有 `dist/filter.exe`；需要使用 `pyinstaller filter.spec` 重新打包。

离线验证：`python -m unittest discover -s tests -v`。测试使用模拟响应，无需账号或校内网络。
