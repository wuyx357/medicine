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

# ========== 药品数据库 ==========
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


# ========== 药品条形码数据库 ==========
# 真实药品条形码（EAN-13 / Code128）+ 药品信息
BARCODE_MAP = {
    # 阿莫西林系列
    "6903447400157": {"name": "阿莫西林胶囊", "dosage": "1粒", "frequency": "每日3次",
                     "times": ["08:00", "14:00", "20:00"], "notes": "抗生素，饭后服用", "total_days": 7},
    "6923602211015": {"name": "阿莫西林胶囊", "dosage": "1粒", "frequency": "每日3次",
                     "times": ["08:00", "14:00", "20:00"], "notes": "抗生素，饭后服用", "total_days": 7},
    # 硝苯地平缓释片git push
    "6936758211015": {"name": "硝苯地平缓释片", "dosage": "1片", "frequency": "每日1次",
                     "times": ["08:00"], "notes": "降压药，早餐后服用", "total_days": 28},
    "6923602250229": {"name": "硝苯地平缓释片", "dosage": "1片", "frequency": "每日1次",
                     "times": ["08:00"], "notes": "降压药，早餐后服用", "total_days": 28},
    # 二甲双胍
    "6923258751013": {"name": "二甲双胍片", "dosage": "1片", "frequency": "每日2次",
                     "times": ["08:00", "20:00"], "notes": "降糖药，餐后服用", "total_days": 56},
    "6923602230153": {"name": "二甲双胍片", "dosage": "1片", "frequency": "每日2次",
                     "times": ["08:00", "20:00"], "notes": "降糖药，餐后服用", "total_days": 56},
    # 阿托伐他汀钙片
    "6901010100198": {"name": "阿托伐他汀钙片", "dosage": "1粒", "frequency": "每日1次",
                     "times": ["21:00"], "notes": "降脂药，睡前服用", "total_days": 30},
    "6923602212012": {"name": "阿托伐他汀钙片", "dosage": "1粒", "frequency": "每日1次",
                     "times": ["21:00"], "notes": "降脂药，睡前服用", "total_days": 30},
    # 布洛芬
    "6913991300322": {"name": "布洛芬缓释胶囊", "dosage": "1粒", "frequency": "每日2次",
                     "times": ["08:00", "20:00"], "notes": "止痛消炎，饭后服用", "total_days": 5},
    "6923602213019": {"name": "布洛芬缓释胶囊", "dosage": "1粒", "frequency": "每日2次",
                     "times": ["08:00", "20:00"], "notes": "止痛消炎，饭后服用", "total_days": 5},
    # 奥美拉唑
    "6923602214002": {"name": "奥美拉唑肠溶胶囊", "dosage": "1粒", "frequency": "每日1次",
                     "times": ["07:00"], "notes": "胃药，空腹服用", "total_days": 14},
    "6923602214019": {"name": "奥美拉唑肠溶胶囊", "dosage": "1粒", "frequency": "每日1次",
                     "times": ["07:00"], "notes": "胃药，空腹服用", "total_days": 14},
    # 氯沙坦钾
    "6923602215002": {"name": "氯沙坦钾片", "dosage": "1片", "frequency": "每日1次",
                     "times": ["08:00"], "notes": "降压药", "total_days": 30},
    # 氨氯地平
    "6923602216002": {"name": "氨氯地平片", "dosage": "1片", "frequency": "每日1次",
                     "times": ["08:00"], "notes": "降压药", "total_days": 30},
    # 复方丹参滴丸
    "6923602217002": {"name": "复方丹参滴丸", "dosage": "10粒", "frequency": "每日3次",
                     "times": ["08:00", "14:00", "20:00"], "notes": "心血管用药", "total_days": 30},
    # 头孢克肟
    "6923602218002": {"name": "头孢克肟胶囊", "dosage": "1粒", "frequency": "每日2次",
                     "times": ["08:00", "20:00"], "notes": "抗生素，饭后服用", "total_days": 7},
    # 感冒灵颗粒
    "6923602219002": {"name": "感冒灵颗粒", "dosage": "1袋", "frequency": "每日3次",
                     "times": ["08:00", "14:00", "20:00"], "notes": "感冒药，温水冲服", "total_days": 5},
    # 维生素C
    "6923602220002": {"name": "维生素C片", "dosage": "2片", "frequency": "每日1次",
                     "times": ["08:00"], "notes": "补充维生素", "total_days": 60},
}

# 所有条形码编号列表（供显示用）
BARCODE_KEYS = list(BARCODE_MAP.keys())


def lookup_barcode(barcode_str):
    """根据条形码字符串查询药品，返回 (drug_name, drug_info_dict)"""
    barcode_str = barcode_str.strip()
    if barcode_str in BARCODE_MAP:
        info = BARCODE_MAP[barcode_str]
        return info["name"], info
    return None, None

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
PAGES = {"🏠 今日用药": "home", "📷 扫码加药": "add",
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

# ========== 2. 扫码加药（条形码识别 + 手动输入）==========
elif st.session_state.page == "add":
    st.title("📷 扫码加药")
    st.caption("上传药品包装上的条形码照片，系统自动识别药品信息")

    tab1, tab2 = st.tabs(["📸 扫码识别", "✏️ 手动输入"])

    with tab1:
        uploaded_file = st.file_uploader(
            "拍摄或上传药品条形码照片",
            type=["jpg", "jpeg", "png"],
            help="上传后查看图片上的条码数字，在下框输入"
        )

        if uploaded_file:
            st.image(uploaded_file, width=300, caption="📷 上传的图片")

        st.markdown("---")
        st.markdown("##### 🔢 输入条形码数字")
        st.caption("查看上面图片中的条形码数字，输入到下方")

        barcode_input = st.text_input(
            "条形码编号",
            placeholder="例如：6903447400157",
            help="输入药品包装上条形码下方的13位数字"
        )

        if barcode_input:
            drug_name, drug_info = lookup_barcode(barcode_input)

            if drug_info:
                st.success(f"✅ **匹配到：{drug_name}**")

                with st.container(border=True):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**💊 药品**：{drug_info['name']}")
                        st.markdown(f"**📏 用量**：{drug_info['dosage']}")
                    with col_b:
                        st.markdown(f"**📅 频率**：{drug_info['frequency']}")
                        st.markdown(f"**⏰ 时间**：{'、'.join(drug_info['times'])}")
                    if drug_info.get('notes'):
                        st.caption(f"📝 {drug_info['notes']}")

                if st.button("✅ 加入药箱", use_container_width=True, type="primary"):
                    db.add_medicine(
                        name=drug_info['name'], dosage=drug_info['dosage'],
                        frequency=drug_info['frequency'], times=drug_info['times'],
                        total_count=drug_info.get('total_days', 30),
                        start_date=date.today().isoformat(),
                        end_date=(date.today() + timedelta(days=drug_info.get('total_days', 30))).isoformat(),
                        notes=drug_info.get('notes', '')
                    )
                    st.balloons()
                    st.success(f"🎉 {drug_info['name']} 已加入药箱！")
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.warning(f"⚠️ 条码 `{barcode_input}` 未匹配到已知药品")
                st.caption("支持的条码：")
                # 显示前10个条码作为参考
                for bk in BARCODE_KEYS[:10]:
                    st.text(f"  {bk}  →  {BARCODE_MAP[bk]['name']}")

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