"""
AI 用药伴侣 - 零自定义CSS版
"""
import streamlit as st
import datetime, os, random, time, requests
from database import Database

st.set_page_config(page_title="AI用药伴侣", page_icon="💊", layout="centered",
                   initial_sidebar_state="collapsed")

DB_PATH = os.path.join(os.path.dirname(__file__), "medicine.db")
if "db" not in st.session_state:
    st.session_state.db = Database(DB_PATH)
    if not st.session_state.db.get_medicines():
        for d in [
            {"name": "硝苯地平缓释片", "dosage": "1片", "frequency": "每日1次",
             "times": ["08:00"], "total_count": 28, "notes": "降压药，早餐后服用"},
            {"name": "二甲双胍片", "dosage": "1片", "frequency": "每日2次",
             "times": ["08:00", "20:00"], "total_count": 56, "notes": "降糖药，餐后服用"},
            {"name": "阿托伐他汀钙片", "dosage": "1粒", "frequency": "每日1次",
             "times": ["21:00"], "total_count": 30, "notes": "降脂药，睡前服用"},
        ]:
            st.session_state.db.add_medicine(**d)

db = st.session_state.db
for key, default in [("page", "home"), ("add_step", 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

PAGES = {"🏠 今日用药": "home", "📷 拍照加药": "add",
         "💊 我的药箱": "cabinet", "🤖 AI问答": "qa"}

cols = st.columns(4)
for i, (label, page) in enumerate(PAGES.items()):
    with cols[i]:
        if st.button(label, use_container_width=True,
                     type="primary" if st.session_state.page == page else "secondary"):
            st.session_state.page = page
            st.rerun()

# ========== 主页 ==========
if st.session_state.page == "home":
    st.title("💊 今日用药")
    now = datetime.datetime.now()
    st.caption(f"{now.strftime('%Y年%m月%d日')} 星期{'一二三四五六日'[now.weekday()]}")

    for o in db.get_overdue():
        st.warning(f"⚠️ {o['medicine_name']} 应在 {o['scheduled_time']} 服用，已超时！")
    for u in db.get_upcoming(30):
        st.info(f"🔔 {u['medicine_name']} {u['scheduled_time']} 即将服药")

    logs = db.get_today_logs()
    if not logs:
        st.info("📭 暂无药品，请先拍照加药")
    else:
        taken = sum(1 for l in logs if l["status"] == "已服")
        missed = sum(1 for l in logs if l["status"] == "漏服")
        pending = len(logs) - taken - missed
        c1, c2, c3 = st.columns(3)
        c1.metric("已服", taken); c2.metric("待服", pending); c3.metric("漏服", missed)

        if taken == len(logs):
            st.success("🎉 太棒了！今日药品已全部服用！")

        now_t = now.strftime("%H:%M")
        for log in logs:
            n, s, stt, lid = log["medicine_name"], log["scheduled_time"], log["status"], log["id"]
            st.markdown(f"**{'🟢' if stt=='已服' else '🔴' if stt=='漏服' else '⚪'} {n}** — {s}")
            if stt == "待服":
                c1, c2 = st.columns(2)
                if c1.button(f"✅ 已服", key=f"tk{lid}"): db.mark_taken(lid); st.rerun()
                if c2.button(f"❌ 漏服", key=f"ms{lid}"): db.mark_missed(lid); st.rerun()
            elif stt == "已服":
                st.caption(f"已于 {log.get('actual_time','')} 服用")
            st.divider()

    st.caption("⏰ 每30秒自动刷新")
    time.sleep(30)
    st.rerun()

# ========== 拍照加药 ==========
elif st.session_state.page == "add":
    st.title("📷 拍照加药")
    DRUGS = {
        "阿莫西林胶囊": ("1粒", "每日3次", ["08:00","14:00","20:00"], "抗生素，饭后服用"),
        "硝苯地平缓释片": ("1片", "每日1次", ["08:00"], "降压药，早餐后服用"),
        "二甲双胍片": ("1片", "每日2次", ["08:00","20:00"], "降糖药，餐后服用"),
        "阿托伐他汀钙片": ("1粒", "每日1次", ["21:00"], "降脂药，睡前服用"),
        "布洛芬缓释胶囊": ("1粒", "每日2次", ["08:00","20:00"], "止痛消炎"),
        "奥美拉唑肠溶胶囊": ("1粒", "每日1次", ["07:00"], "胃药，空腹服用"),
        "氯沙坦钾片": ("1片", "每日1次", ["08:00"], "降压药"),
        "氨氯地平片": ("1片", "每日1次", ["08:00"], "降压药"),
        "复方丹参滴丸": ("10粒", "每日3次", ["08:00","14:00","20:00"], "心血管用药"),
    }
    KW = {"阿莫西":"阿莫西林胶囊","硝苯":"硝苯地平缓释片","二甲双":"二甲双胍片",
          "布洛芬":"布洛芬缓释胶囊","奥美":"奥美拉唑肠溶胶囊","氯沙":"氯沙坦钾片",
          "氨氯":"氨氯地平片","复方丹参":"复方丹参滴丸","丹参":"复方丹参滴丸"}

    def sim(img=None):
        names = list(DRUGS.keys())
        if img: random.seed(sum(img[:100]))
        n = names[random.randint(0,len(names)-1)]
        d,f,t,nt = DRUGS[n]
        return {"name":n,"confidence":round(random.uniform(0.82,0.99),2),
                "dosage":d,"frequency":f,"times":t,"notes":nt}

    def match(t):
        t = t.strip()
        if t in DRUGS: return t
        for k,v in KW.items():
            if k in t: return v
        return t

    step = st.session_state.add_step
    if step == 0:
        st.info("📸 上传药品照片，AI自动识别")
        up = st.file_uploader("选择照片", type=["jpg","jpeg","png"], label_visibility="collapsed")
        if up:
            with st.spinner("识别中..."):
                time.sleep(1.5)
                st.session_state.rec = sim(up.getvalue())
            st.session_state.add_step = 1
            st.rerun()
        st.caption("或直接输入药名：")
        m = st.text_input("药名", placeholder="阿莫西林胶囊", label_visibility="collapsed")
        if m:
            name = match(m)
            if name in DRUGS:
                d,f,t,n = DRUGS[name]
                st.session_state.rec = {"name":name,"confidence":1.0,"dosage":d,"frequency":f,"times":t,"notes":n}
            else:
                st.session_state.rec = {"name":name,"confidence":1.0,"dosage":"1粒","frequency":"每日1次","times":["08:00"],"notes":""}
            st.session_state.add_step = 1
            st.rerun()

    elif step == 1:
        r = st.session_state.rec
        st.success(f"识别结果：**{r['name']}**（可信度 {r['confidence']*100:.0f}%）")
        name = st.text_input("药品名称", r["name"])
        c1,c2 = st.columns(2)
        if c1.button("✅ 下一步", use_container_width=True):
            r["name"] = name; st.session_state.add_step = 2; st.rerun()
        if c2.button("🔄 重新识别", use_container_width=True):
            st.session_state.add_step = 0; st.rerun()

    elif step == 2:
        r = st.session_state.rec
        st.markdown(f"**💊 {r['name']}**")
        st.info("AI推荐用药计划，可修改：")
        dosage = st.text_input("每次用量", r["dosage"])
        freq_opts = ["每日1次","每日2次","每日3次","自定义"]
        fi = freq_opts.index(r["frequency"]) if r["frequency"] in freq_opts else 0
        freq = st.selectbox("频率", freq_opts, index=fi)
        T = {"每日1次":["08:00"],"每日2次":["08:00","20:00"],"每日3次":["08:00","14:00","20:00"]}
        if freq == "自定义":
            ts = st.text_input("时间（逗号分隔）", ",".join(r["times"]))
            times = [t.strip() for t in ts.split(",") if t.strip()]
        else:
            times = T[freq]; st.caption(f"建议时间：{'、'.join(times)}")
        total = st.number_input("总数量（粒/片）", 1, 999, r.get("total_count",30), step=10)
        notes = st.text_area("备注", r.get("notes",""))
        if st.button("💾 加入药箱", use_container_width=True):
            db.add_medicine(name=r["name"],dosage=dosage,frequency=freq,times=times,total_count=total,notes=notes)
            st.balloons(); st.success(f"✅ 已加入药箱！")
            st.session_state.add_step = 0
            time.sleep(1.5); st.session_state.page="home"; st.rerun()

# ========== 药箱 ==========
elif st.session_state.page == "cabinet":
    st.title("💊 我的药箱")
    meds = db.get_medicines()
    if not meds:
        st.info("📭 药箱为空")
    else:
        st.caption(f"共 {len(meds)} 种，剩余 {sum(m['total_count'] for m in meds)} 粒")
        if "edit_id" not in st.session_state: st.session_state.edit_id = None
        now_t = datetime.datetime.now().strftime("%H:%M")

        for m in meds:
            mid = m["id"]
            if st.session_state.edit_id == mid:
                st.markdown(f"**✏️ {m['name']}**")
                n = st.text_input("名称", m["name"], key=f"en{mid}")
                d = st.text_input("用量", m["dosage"], key=f"ed{mid}")
                fo = ["每日1次","每日2次","每日3次","自定义"]
                fi = fo.index(m["frequency"]) if m["frequency"] in fo else 0
                f = st.selectbox("频率", fo, index=fi, key=f"ef{mid}")
                T = {"每日1次":["08:00"],"每日2次":["08:00","20:00"],"每日3次":["08:00","14:00","20:00"]}
                if f == "自定义":
                    ts = st.text_input("时间", ",".join(m["times"]), key=f"et{mid}")
                    times = [t.strip() for t in ts.split(",") if t.strip()]
                else:
                    times = T[f]
                cnt = st.number_input("剩余", m["total_count"], 0, key=f"ec{mid}")
                nt = st.text_area("备注", m.get("notes",""), key=f"nn{mid}")
                c1,c2 = st.columns(2)
                if c1.button("保存", key=f"sv{mid}"): db.update_medicine(mid,name=n,dosage=d,frequency=f,times=times,total_count=cnt,notes=nt); st.session_state.edit_id=None; st.rerun()
                if c2.button("取消", key=f"cl{mid}"): st.session_state.edit_id=None; st.rerun()
            else:
                ts = "、".join(m["times"])
                nx = next((t for t in m["times"] if t >= now_t), "明天 "+m["times"][0]) if m["times"] else "无"
                st.markdown(f"**💊 {m['name']}**  {m['frequency']}  {m['dosage']}")
                st.caption(f"🕐 {ts} 📦 剩余 {m['total_count']} 🔔 下次 {nx}")
                if m.get("notes"): st.caption(f"📝 {m['notes']}")
                c1,c2 = st.columns(2)
                if c1.button("编辑", key=f"ed{mid}"): st.session_state.edit_id=mid; st.rerun()
                if c2.button("删除", key=f"de{mid}"): db.delete_medicine(mid); st.rerun()
            st.divider()

# ========== AI问答 ==========
elif st.session_state.page == "qa":
    st.title("🤖 AI用药问答")
    st.info("可以问我任何用药问题")

    SIM = {
        "血压":"💊 降压药：每天固定时间服用，不要自行停药。忘记就尽快补服，接近下次时间则跳过。",
        "血糖":"💊 降糖药：随餐服用，定时测血糖。心慌出冷汗立即吃糖。",
        "忘记":"😅 想起就补服，快下次了就跳过，不要一次吃双倍！",
        "副作用":"💊 头晕→观察，胃不适→饭后服，皮疹→就医。严重请停药。",
        "间隔":"⏰ 每日1次→24小时，每日2次→12小时，每日3次→6-8小时。",
    }

    for q in ["降压药怎么吃？","忘记吃药了怎么办？","药物副作用？"]:
        if st.button(q): st.session_state._ask=q; st.rerun()

    if st.session_state.get("_ask"):
        q = st.session_state._ask; st.session_state._ask=""
        db.add_chat_message("user", q)
        ans = "（没找到匹配）"
        for k,v in SIM.items():
            if k in q: ans = v; break
        if ans == "（没找到匹配）": ans = f"关于「{q}」，建议咨询医生。"
        db.add_chat_message("assistant", ans)
        st.rerun()

    inp = st.text_input("输入问题", label_visibility="collapsed")
    if inp:
        with st.spinner("思考中..."):
            db.add_chat_message("user", inp)
            ans = "（没找到匹配）"
            for k,v in SIM.items():
                if k in inp: ans = v; break
            if ans == "（没找到匹配）": ans = f"关于「{inp}」，建议咨询医生。"
            db.add_chat_message("assistant", ans)
        st.rerun()

    for msg in db.get_chat_history(30):
        st.chat_message("user" if msg["role"]=="user" else "assistant").write(msg["content"])

    if db.get_chat_history(1) and st.button("🗑️ 清空对话"):
        db.clear_chat_history(); st.rerun()
