# LiveSlides：PPT 转 HTML 电子画册与离线播放器

LiveSlides 是本地优先的 PowerPoint 宣传册转换工具。将定稿 PPTX 转为可在线阅读、二维码分享、离线循环播放的 HTML 画册，不自动编写内容，不猜测页面语义。

项目：https://github.com/RickeyHuangHub/LiveSlides

阶段：Phase 1 开发原型（0.1.0），不是已完成鉴权的多租户 SaaS。

## 适用场景与功能

适合企业介绍、产品目录、展会大屏、销售演示和手机扫码阅读。支持明确规则的页面拆分、独立封面、电脑双页、手机逐半页、Page Curl、自动循环、纯净演示、多公司配置、JSON、PNG 二维码与离线包。

原 PPT 图片中的文字与 Logo 保持原内容；网页品牌配置不会重写这些图片。采用 LibreOffice → PDF → PyMuPDF → WebP 流程，不需要 LLM 或付费 AI API。

## 安装与使用

按[主 README](../README.md#quick-start-windows)的 Windows 步骤安装。需要 Python、Node/npm、LibreOffice 和源字体。当前转换器使用固定 Windows LibreOffice 路径，尚未配置跨平台转换。

打开 http://127.0.0.1:5193/ → 上传不超过 50MB 的 PPTX → 选择模式 → 转换 → 保存公司／画册配置 → 发布二维码或下载离线包。

离线 ZIP 解压后，用现代浏览器打开“开始播放.html”，无需网络、Python、Node 或本地服务。全屏需用户点击；离线 HTML 不是 MP4。另提供「导出 MP4」功能：1080p 高清静态切页视频（需 FFmpeg），不是卷页动画录屏；网络视频直链不支持离线打包。

## 边界

没有登录及租户权限隔离，仅适合可信局域网开发。手机横屏锁定尚未实现。字体差异可能影响版式，PPT 动画与声音不会保留。手机文件预览器未必执行 HTML，需要真实设备验收。

本仓库不包含客户 PPT/PDF、画册图片、离线包或公司私有配置；尚未选择项目开源许可证。

## 文档

- [离线播放](offline-player.md)
- [多公司配置与动态路由](multi-tenant.md)
- [响应式阅读](responsive-reading.md)
- [功能事实与 FAQ](project-facts.md)
- [AI 可读文档索引](../llms.txt)

关键词：PPT 转网页、PPTX 转 HTML、电子画册、数字宣传册、产品目录、仿真翻页、手机扫码阅读、离线演示、企业展陈。
