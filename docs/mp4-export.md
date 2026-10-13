# MP4 视频导出 / MP4 export

在公司配置侧栏选择 PPT 画册 →「导出 MP4」→ 等待生成状态完成 →「下载 MP4（1080p）」。生成任务在后台执行，同时仅允许一个编码任务。

当前输出 H.264 / MP4，1920×1080、30fps、yuv420p、CRF 18、无音轨，使用 faststart 便于播放器加载。每个源 Slide 的左右半页按顺序拼合，等比例放入画面，不拉伸；左半页封面模式先展示居中独立封面。普通静止时间沿用画册 interval，末页沿用 loopDelay。

**这是高清静态切页视频，不是 Page Curl 浏览器录屏。** MP4 不包含交互、二维码、自动隐藏按钮或源 PPT 动画。视频只编码一轮，循环由 VLC、系统播放器或展陈播放器设置。离线 HTML 包则保留交互翻页和自身循环逻辑。

需要安装支持 libx264 的 FFmpeg，并放入 PATH，或设置 LIVESLIDES_FFMPEG 为 ffmpeg 可执行文件完整路径。服务端不会自动下载编码器。已有网络视频不转码；暂不支持视频直链导出。

API: POST /api/video-export with {tenantId,catalogId} returns a job id. GET /api/video-export/:id returns status. GET /api/video-export/:id/download downloads the completed MP4. Jobs are in memory and are lost on API restart; encoded files remain in runtime-videos/. No production authentication is provided.

Conversion uses existing image pages, so it does not recover detail absent from raster input. Rendering and H.264 encoding may slightly change pixels. Source and third-party licensing still apply; FFmpeg licensing depends on the installed build.
