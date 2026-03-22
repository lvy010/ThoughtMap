
### 3.21
- 分类统一为：blog（博客）/link（链接），历史 disconnected 仅做兼容读，保存时迁移为 link。
- 顺序调整触发方式：长按整卡 3 秒（桌面+移动一致）。
- 长按后进入拖拽态（阴影/缩放/抓手光标），拖动排序，松手落位。
- 排序后出现“有未保存更改”状态，必须点击“保存”才持久化。
- 拖拽、编辑、删除、添加、保存全部限制为已认证密钥用户

### 3.22
[×]并不好看
- 将 description 从 line-clamp-3 改为单行省略：overflow-hidden + text-ellipsis + whitespace-nowrap
- 增加 title={randomItem.description}，鼠标悬浮可看完整文本（原生 tooltip）