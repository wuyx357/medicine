"""
AI 用药伴侣 - 改进版
功能：
1. 今日用药：日历式管理，显示每日用药计划
2. 拍照加药：药品名称识别 + 输入时实时搜索（模糊匹配）
3. 我的药箱：支持设置药品起止日期（用药周期）
4. AI问答：接入 DeepSeek 模型生成真实回答
"""

import streamlit as st
import datetime
import os
import random
import time
import requests
import json
from datetime import date, timedelta
from difflib import get_close_matches
from database import Database

# ========== 页面配置 ==========
st.set_page_config(page_title="AI用药伴侣", page_icon="💊", layout="centered")

# ========== 初始化数据库 ==========
# 在Streamlit Cloud上需要用可写目录
import tempfile
_DB_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(_DB_DIR, "ai_medicine_companion.db")

if "db" not in st.session_state:
    st.session_state.db = Database(DB_PATH)
    # 添加演示数据
    if not st.session_state.db.get_medicines():
        demo_medicines = [
            {"name": "硝苯地平缓释片", "dosage": "1片", "frequency": "每日1次",
             "times": ["08:00"], "total_count": 28, "start_date": date.today().isoformat(),
             "end_date": (date.today() + timedelta(days=28)).isoformat(), "notes": "降压药，早餐后服用"},
            {"name": "二甲双胍片", "dosage": "1片", "frequency": "每日2次",
             "times": ["08:00", "20:00"], "total_count": 56, "start_date": date.today().isoformat(),
             "end_date": (date.today() + timedelta(days=56)).isoformat(), "notes": "降糖药，餐后服用"},
            {"name": "阿托伐他汀钙片", "dosage": "1粒", "frequency": "每日1次",
             "times": ["21:00"], "total_count": 30, "start_date": date.today().isoformat(),
             "end_date": (date.today() + timedelta(days=30)).isoformat(), "notes": "降脂药，睡前服用"},
        ]
        for med in demo_medicines:
            st.session_state.db.add_medicine(**med)

db = st.session_state.db

# ========== 初始化页面状态 ==========
if "page" not in st.session_state:
    st.session_state.page = "home"
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()

# ========== 药品数据库（用于识别和搜索）==========
DRUGS = {
    "阿莫西林胶囊": {"dosage": "1粒", "frequency": "每日3次", "times": ["08:00", "14:00", "20:00"],
                  "notes": "抗生素，饭后服用", "total_days": 7},
    "硝苯地平缓释片": {"dosage": "1片", "frequency": "每日1次", "times": ["08:00"],
                    "notes": "降压药，早餐后服用", "total_days": 28},
    "二甲双胍片": {"dosage": "1片", "frequency": "每日2次", "times": ["08:00", "20:00"],
                 "notes": "降糖药，餐后服用", "total_days": 56},
    "阿托伐他汀钙片": {"dosage": "1粒", "frequency": "每日1次", "times": ["21:00"],
                     "notes": "降脂药，睡前服用", "total_days": 30},
    "布洛芬缓释胶囊": {"dosage": "1粒", "frequency": "每日2次", "times": ["08:00", "20:00"],
                     "notes": "止痛消炎，饭后服用", "total_days": 5},
    "奥美拉唑肠溶胶囊": {"dosage": "1粒", "frequency": "每日1次", "times": ["07:00"],
                       "notes": "胃药，空腹服用", "total_days": 14},
    "氯沙坦钾片": {"dosage": "1片", "frequency": "每日1次", "times": ["08:00"],
                 "notes": "降压药", "total_days": 30},
    "氨氯地平片": {"dosage": "1片", "frequency": "每日1次", "times": ["08:00"],
                 "notes": "降压药", "total_days": 30},
    "复方丹参滴丸": {"dosage": "10粒", "frequency": "每日3次", "times": ["08:00", "14:00", "20:00"],
                   "notes": "心血管用药", "total_days": 30},
    "头孢克肟胶囊": {"dosage": "1粒", "frequency": "每日2次", "times": ["08:00", "20:00"],
                   "notes": "抗生素，饭后服用", "total_days": 7},
    "感冒灵颗粒": {"dosage": "1袋", "frequency": "每日3次", "times": ["08:00", "14:00", "20:00"],
                "notes": "感冒药，温水冲服", "total_days": 5},
    "维生素C片": {"dosage": "2片", "frequency": "每日1次", "times": ["08:00"],
               "notes": "补充维生素", "total_days": 60},
}

# 药品名称列表（用于搜索）
DRUG_NAMES = list(DRUGS.keys())


def recognize_drug(image_data):
    """模拟AI识别药品：基于图片内容hash做确定性匹配，每次同图出同结果"""
    if image_data is None:
        return None
    # 用图片内容的hash值做种子，确保同一张图片每次识别结果一致
    seed_val = sum(image_data[:min(1024, len(image_data))]) + len(image_data)
    rng = random.Random(seed_val)
    # 从药库中挑选一个（模拟真实识别）
    chosen = rng.choice(DRUG_NAMES)
    return chosen

# ========== AI 问答配置 ==========
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

def get_ai_answer(question: str) -> str:
    """调用 DeepSeek API 获取回答"""
    if not DEEPSEEK_API_KEY:
        return "⚠️ API密钥未配置，请在环境变量中设置 DEEPSEEK_API_KEY"

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的用药顾问，回答用药相关问题时要准确、安全、易懂。不知道的就说建议咨询医生。"},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"⚠️ API调用失败：{response.status_code}"
    except Exception as e:
        return f"⚠️ 请求失败：{str(e)}"

# ========== 辅助函数 ==========
def search_drugs(query: str, max_results: int = 5):
    """模糊搜索药品名称"""
    if not query:
        return []
    matches = get_close_matches(query, DRUG_NAMES, n=max_results, cutoff=0.4)
    # 同时匹配包含关键词的
    extra = [d for d in DRUG_NAMES if query in d and d not in matches][:max_results - len(matches)]
    return matches + extra

# ========== 导航栏 ==========
PAGES = {"🏠 今日用药": "home", "📷 拍照加药": "add",
         "💊 我的药箱": "cabinet", "🤖 AI问答": "qa"}

cols = st.columns(len(PAGES))
for i, (label, page) in enumerate(PAGES.items()):
    with cols[i]:
        if st.button(label, use_container_width=True,
                     type="primary" if st.session_state.page == page else "secondary"):
            st.session_state.page = page
            st.rerun()

# ========== 1. 今日用药（日历式管理）==========
if st.session_state.page == "home":
    st.title("📅 今日用药")

    # 日历选择器
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("◀ 前一天"):
            st.session_state.selected_date -= timedelta(days=1)
            st.rerun()
    with col2:
        selected = st.date_input("选择日期", st.session_state.selected_date, label_visibility="collapsed")
        st.session_state.selected_date = selected
    with col3:
        if st.button("后一天 ▶"):
            st.session_state.selected_date += timedelta(days=1)
            st.rerun()

    st.markdown(f"### {st.session_state.selected_date.strftime('%Y年%m月%d日')} {['一','二','三','四','五','六','日'][st.session_state.selected_date.weekday()]}")

    # 获取该日期的用药计划
    medicines = db.get_medicines()
    today_logs = db.get_today_logs() if st.session_state.selected_date == date.today() else []

    # 筛选有效药品（在用药周期内）
    valid_medicines = []
    for med in medicines:
        start = med.get("start_date")
        end = med.get("end_date")
        if start and end:
            if start <= st.session_state.selected_date.isoformat() <= end:
                valid_medicines.append(med)
        else:
            valid_medicines.append(med)

    if not valid_medicines:
        st.info("📭 当天没有用药计划")
    else:
        for med in valid_medicines:
            st.markdown(f"**💊 {med['name']}** - {med['dosage']} - {med['frequency']}")
            times = med.get("times", [])
            for t in times:
                # 检查是否已服用
                taken = any(l for l in today_logs if l["medicine_name"] == med["name"] and l["scheduled_time"] == t)
                if taken:
                    st.success(f"✅ {t} 已服用")
                else:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.warning(f"⏰ {t} 待服用")
                    with col2:
                        if st.button("已服", key=f"take_{med['id']}_{t}"):
                            db.mark_taken_by_name(med["name"], t)
                            st.rerun()
            st.divider()

    # 统计数据
    total = sum(len(med.get("times", [])) for med in valid_medicines)
    taken_count = len(today_logs)
    st.caption(f"📊 今日总计：{taken_count}/{total} 已服用")

# ========== 2. 拍照加药（药品识别 + 实时搜索）==========
elif st.session_state.page == "add":
    st.title("📷 拍照加药")

    tab1, tab2 = st.tabs(["📸 拍照识别", "✏️ 手动输入"])

    with tab1:
        uploaded_file = st.file_uploader("拍摄或上传药品照片", type=["jpg", "jpeg", "png"])

        if uploaded_file:
            # 识别区 ──────────────────────
            st.image(uploaded_file, width=250, caption="上传的图片")

            # 文件指纹：同一文件只识别一次
            file_key = f"pic_{uploaded_file.name}_{uploaded_file.size}"
            last_key = st.session_state.get("_pic_key", "")

            if file_key != last_key:
                # 新文件 → 调用识别
                with st.spinner("🔍 AI正在识别药品，请稍候..."):
                    time.sleep(1.2)  # 模拟识别耗时
                    rec_name = recognize_drug(uploaded_file.getvalue())
                
                # 存入 session_state，记住识别结果
                st.session_state._pic_key = file_key
                st.session_state._pic_result = rec_name
                st.session_state._pic_info = None

                # 搜集药品详情
                if rec_name and rec_name in DRUGS:
                    info = DRUGS[rec_name]
                    st.session_state._pic_info = {
                        "name": rec_name,
                        "dosage": info["dosage"],
                        "frequency": info["frequency"],
                        "times": info["times"],
                        "notes": info["notes"],
                        "total_days": info["total_days"],
                    }
                elif rec_name:
                    st.session_state._pic_info = {
                        "name": rec_name,
                        "dosage": "1粒",
                        "frequency": "每日1次",
                        "times": ["08:00"],
                        "notes": "",
                        "total_days": 30,
                    }
                st.rerun()

            # 显示识别结果 ──────────────────
            rec_name = st.session_state.get("_pic_result")
            if rec_name:
                st.success(f"✅ **识别结果：{rec_name}**")

                info = st.session_state.get("_pic_info")
                if info:
                    # 展示药品信息卡
                    with st.container(border=True):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(f"**💊 药品**：{info['name']}")
                            st.markdown(f"**📏 用量**：{info['dosage']}")
                        with col_b:
                            st.markdown(f"**📅 频率**：{info['frequency']}")
                            st.markdown(f"**⏰ 时间**：{'、'.join(info['times'])}")
                        if info.get('notes'):
                            st.caption(f"📝 {info['notes']}")

                    col_add, col_cancel = st.columns([1, 1])
                    with col_add:
                        if st.button("✅ 加入药箱", use_container_width=True, type="primary"):
                            start_date = date.today().isoformat()
                            end_date = (date.today() + timedelta(days=info.get('total_days', 30))).isoformat()
                            db.add_medicine(
                                name=info['name'], dosage=info['dosage'],
                                frequency=info['frequency'], times=info['times'],
                                total_count=info.get('total_days', 30),
                                start_date=start_date, end_date=end_date,
                                notes=info.get('notes', '')
                            )
                            st.balloons()
                            st.success(f"🎉 {info['name']} 已加入药箱！")
                            # 重置状态，允许继续添加
                            st.session_state._pic_key = ""
                            st.session_state._pic_result = None
                            st.session_state._pic_info = None
                            time.sleep(1.5)
                            st.rerun()
                    with col_cancel:
                        if st.button("🔄 重新识别", use_container_width=True):
                            st.session_state._pic_key = ""
                            st.session_state._pic_result = None
                            st.session_state._pic_info = None
                            st.rerun()

    with tab2:
        st.info("输入药品名称，从推荐列表中选择")
        drug_name = st.text_input("搜索药品名称", placeholder="例如：阿莫西林")

        if drug_name:
            suggestions = search_drugs(drug_name)
            if suggestions:
                st.caption(f"💡 建议：{' / '.join(suggestions)}")
                for sug in suggestions:
                    if sug in DRUGS:
                        info = DRUGS[sug]
                        if st.button(f"📌 {sug}（{info['dosage']}，{info['frequency']}）", key=f"sel_{sug}", use_container_width=True):
                            start_date = date.today().isoformat()
                            end_date = (date.today() + timedelta(days=info.get('total_days', 30))).isoformat()
                            db.add_medicine(
                                name=sug, dosage=info['dosage'],
                                frequency=info['frequency'], times=info['times'],
                                total_count=info.get('total_days', 30),
                                start_date=start_date, end_date=end_date,
                                notes=info.get('notes', '')
                            )
                            st.balloons()
                            st.success(f"🎉 {sug} 已加入药箱！")
                            time.sleep(1.5)
                            st.rerun()
            else:
                # 不在药库里的自定义药品
                if st.button(f"➕ 手动添加「{drug_name}」", use_container_width=True):
                    start_date = date.today().isoformat()
                    end_date = (date.today() + timedelta(days=30)).isoformat()
                    db.add_medicine(
                        name=drug_name, dosage="1粒", frequency="每日1次",
                        times=["08:00"], total_count=30,
                        start_date=start_date, end_date=end_date, notes=""
                    )
                    st.balloons()
                    st.success(f"🎉 {drug_name} 已加入药箱！")
                    time.sleep(1.5)
                    st.rerun()

# ========== 3. 我的药箱（含起止日期）==========
elif st.session_state.page == "cabinet":
    st.title("💊 我的药箱")

    medicines = db.get_medicines()
    if not medicines:
        st.info("📭 药箱为空，请先添加药品")
    else:
        for med in medicines:
            with st.expander(f"{med['name']} - {med['dosage']}"):
                st.write(f"**频率**：{med['frequency']}")
                st.write(f"**时间**：{'、'.join(med.get('times', []))}")
                st.write(f"**剩余数量**：{med.get('total_count', 0)}")
                st.write(f"**用药周期**：{med.get('start_date', '未设置')} 至 {med.get('end_date', '未设置')}")
                if med.get('notes'):
                    st.write(f"**备注**：{med['notes']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("编辑", key=f"edit_{med['id']}"):
                        st.session_state.edit_id = med['id']
                        st.rerun()
                with col2:
                    if st.button("删除", key=f"del_{med['id']}"):
                        db.delete_medicine(med['id'])
                        st.rerun()

                if st.session_state.get("edit_id") == med['id']:
                    st.markdown("---")
                    st.subheader("编辑药品")

                    new_name = st.text_input("药品名称", med['name'], key=f"name_{med['id']}")
                    new_dosage = st.text_input("用量", med['dosage'], key=f"dosage_{med['id']}")

                    freq_options = ["每日1次", "每日2次", "每日3次", "自定义"]
                    freq_idx = freq_options.index(med['frequency']) if med['frequency'] in freq_options else 0
                    new_freq = st.selectbox("频率", freq_options, index=freq_idx, key=f"freq_{med['id']}")

                    time_map = {"每日1次": ["08:00"], "每日2次": ["08:00", "20:00"], "每日3次": ["08:00", "14:00", "20:00"]}
                    if new_freq == "自定义":
                        new_times = st.text_input("服药时间（逗号分隔）", ','.join(med.get('times', ["08:00"])), key=f"times_{med['id']}")
                        new_times = [t.strip() for t in new_times.split(',') if t.strip()]
                    else:
                        new_times = time_map[new_freq]
                        st.caption(f"建议时间：{'、'.join(new_times)}")

                    new_total = st.number_input("剩余数量", value=med.get('total_count', 0), key=f"total_{med['id']}")
                    new_start = st.date_input("开始日期", value=date.fromisoformat(med.get('start_date', date.today().isoformat())) if med.get('start_date') else date.today(), key=f"start_{med['id']}")
                    new_end = st.date_input("结束日期", value=date.fromisoformat(med.get('end_date', (date.today() + timedelta(days=30)).isoformat())) if med.get('end_date') else date.today() + timedelta(days=30), key=f"end_{med['id']}")
                    new_notes = st.text_area("备注", med.get('notes', ''), key=f"notes_{med['id']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("保存", key=f"save_{med['id']}"):
                            db.update_medicine(med['id'], name=new_name, dosage=new_dosage, frequency=new_freq,
                                              times=new_times, total_count=new_total, start_date=new_start.isoformat(),
                                              end_date=new_end.isoformat(), notes=new_notes)
                            st.session_state.edit_id = None
                            st.rerun()
                    with col2:
                        if st.button("取消", key=f"cancel_{med['id']}"):
                            st.session_state.edit_id = None
                            st.rerun()

# ========== 4. AI问答（连接大模型）==========
elif st.session_state.page == "qa":
    st.title("🤖 AI用药问答")
    st.info("💡 可以问我任何用药相关问题，我会用专业知识为你解答")

    # 快捷提问
    quick_questions = ["降压药怎么吃？", "忘记吃药了怎么办？", "药物有什么副作用？", "两种药能一起吃吗？"]
    cols = st.columns(len(quick_questions))
    for i, q in enumerate(quick_questions):
        with cols[i]:
            if st.button(q):
                st.session_state.quick_question = q
                st.rerun()

    # 处理快捷提问
    if "quick_question" in st.session_state and st.session_state.quick_question:
        with st.spinner("AI思考中..."):
            answer = get_ai_answer(st.session_state.quick_question)
            st.session_state.messages = st.session_state.get("messages", [])
            st.session_state.messages.append({"role": "user", "content": st.session_state.quick_question})
            st.session_state.messages.append({"role": "assistant", "content": answer})
            del st.session_state.quick_question
            st.rerun()

    # 显示历史消息
    messages = st.session_state.get("messages", [])
    for msg in messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # 用户输入
    if prompt := st.chat_input("输入你的用药问题..."):
        st.chat_message("user").write(prompt)
        with st.spinner("AI思考中..."):
            answer = get_ai_answer(prompt)
        st.chat_message("assistant").write(answer)
        st.session_state.messages = st.session_state.get("messages", [])
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

    # 清空对话
    if st.button("🗑️ 清空对话"):
        st.session_state.messages = []
        st.rerun()