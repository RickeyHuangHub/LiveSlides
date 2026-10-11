# 多公司配置与稳定分享路由

接口类型见 `src/config.d.ts`，运行时字段校验由 `tenant_store.py` 执行。公司身份用 tenant.id，画册身份用 (tenantId, catalog.id)；不同公司可使用相同画册 ID。

## 使用

1. 打开制作页 `/`，在公司配置侧栏添加公司，编辑名称、Logo URL、标语、六位 HEX 主色调与背景图 URL。
2. 添加画册，选择已转换的 PPT 或填写浏览器可播放的视频直链。新转换的画册会在发布时注册到当前公司；也可以在侧栏中将现有画册 ID 绑定到新转换的资产，保留旧二维码。
3. 保存后打开播放页，或点击发布获取二维码。二维码为约 1024 像素的 PNG（库可能按模块网格取整），包含 `/v/:tenantId/:catalogId`。
4. JSON 编辑器可载入当前完整配置，编辑并校验保存；这是完整替换操作，应先保留导出的配置。

配置首次从已有画册生成 default 公司预设；保存后落盘至项目根目录 `tenant-config.json`。这个文件应备份，不提交版本控制。原 PPT 图片不重绘，品牌配置不会替换图片内部的文字或 Logo。

```json
{
  "tenants": [{"id":"acme","name":"示例公司","logoUrl":"","slogan":"产品与服务","primaryColor":"#336699","backgroundUrl":""}],
  "catalogs": [{"id":"showroom","tenantId":"acme","title":"展厅视频","mediaType":"video","albumId":"","videoUrl":"https://your-domain.example/media/showroom.mp4"}]
}
```

## API

- GET /api/config：读取配置；POST /api/config：校验并原子保存完整配置（最大 256KB）。
- GET /api/album-list：列出可绑定资产。
- GET /api/view/:tenantId/:catalogId：读取对应公司及画册；不存在则 404，不回退其他公司。
- POST /api/catalog-publish：请求 `{tenantId,catalogId}`，返回动态播放 URL。
- 原 `/api/publish` 仅在资产对应唯一画册配置时兼容，返回新动态路由；歧义返回 409。

## 播放与部署边界

播放页没有配置侧栏，画册保持自动循环、控件自动隐藏。公司 Logo、名称、标语仅在唤起的工具栏出现；配置背景图时优先使用它作为舞台与环境光图像，未配置则使用当前页面生成环境光。视频静音自动循环（声音由用户启用）；浏览器若阻止自动全屏，可点击“全屏”。自动播放失败显示可点击的重试提示。

默认分享地址由 LAN IP + LIVESLIDES_VIEWER_PORT（5193）生成。生产域名使用环境变量 LIVESLIDES_PUBLIC_BASE_URL。环境变量不是部署操作：生产服务器还需将 `/v/*` 回退到 index.html，并代理 `/api/*` 到 Python API。资源直链需实际可访问，HTTPS 网站的视频和图片也应使用 HTTPS。

本阶段是配置驱动的多公司管理，不是带账户权限的 SaaS。配置管理接口尚无登录鉴权；仅用于可信局域网开发环境。正式公开部署前必须限制管理接口、加入登录授权，公开播放端仅开放只读播放/资产接口。公司 ID 不是访问密钥，知道链接的人可打开公开画册。

## 回归

`python -m unittest test_tenant_store -v` 覆盖配置保存、重复 ID、路径/URL 校验、公司范围查询、迁移与稳定 ID 换内容；`npm run build` 验证前端构建。

2026-10-09：8 项自动化测试及生产构建通过；浏览器验证配置状态更新、JSON 保存、动态路由刷新、自动翻页、控制栏隐藏及二维码生成。生成的 PNG 实测为 1023×1023。下载按钮已接入，但内嵌浏览器自动化未返回下载完成事件；实际手机扫码与真实视频素材播放尚未实测。
