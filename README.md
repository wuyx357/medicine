# AI 用药伴侣 Demo

面向 55-75 岁中老年人的智能用药管理工具。

## 功能

| 页面 | 功能 |
|------|------|
| 🏠 **今日用药** | 按时间显示今日待服药品，支持标记已服/漏服，超时提醒 |
| 📷 **拍照加药** | 上传药品照片→AI识别→确认药名→推荐用药计划→加入药箱 |
| 💊 **我的药箱** | 列表展示所有药品，支持编辑/删除，显示下次提醒时间 |
| 🤖 **AI问答** | 用药问题智能回答（可接DeepSeek API），内置常见问题快捷按钮 |

## 快速启动

```bash
# 1. 进入项目目录
cd ai-medicine-companion

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`

## 首次使用

启动后自带 3 种演示药品（降压药、降糖药、降脂药），可直接在「今日用药」页体验标记服药。

想加新药？点击「拍照加药」：
1. 上传药品包装照片（或用文字输入药名）
2. AI "识别"后确认药名
3. AI 推荐用药计划，可编辑
4. 加入药箱

## 连接 DeepSeek API（可选）

在「AI问答」页底部展开「DeepSeek API设置」，填入 API Key：

```
sk-你的DeepSeekKey
```

不填则使用内置的模拟回答。

## 分享链接

### 方法一：Streamlit Community Cloud（推荐，已免费）

1. 把项目传到 GitHub
2. 登录 https://share.streamlit.io
3. 连接仓库部署
4. 获得公网链接如 `https://xxx.streamlit.app`

### 方法二：ngrok（临时分享）

```bash
# 启动本地服务
streamlit run app.py --server.port 8501

# 新开终端，启动 ngrok
ngrok http 8501
```

获得 `https://xxxx.ngrok.io` 链接，分享给他人即可。

### 方法三：部署到服务器

```bash
# 后台运行
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &
```

然后通过 `http://你的IP:8501` 访问。

## 项目结构

```
ai-medicine-companion/
├── app.py           # 主程序（Streamlit 所有页面）
├── database.py      # SQLite 数据库操作
├── requirements.txt # 依赖
├── medicine.db      # 自动生成的数据库
└── README.md        # 本文件
```

## 技术栈

- **前端/后端**: Python + Streamlit
- **数据库**: SQLite
- **AI 识别**: 模拟识别（内置 12 种常见药品）
- **AI 问答**: 内置模拟回答 + 可接入 DeepSeek API
- **存储**: 本地 SQLite 文件，无需配置
"# medicine" 
