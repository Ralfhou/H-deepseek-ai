import streamlit as st
from openai import OpenAI
import json

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 智能审计 Agent", page_icon="🕵️‍♂️", layout="wide")

api_key = st.secrets.get("DEEPSEEK_API_KEY")
if not api_key:
    st.error("❌ 请在 Streamlit Secrets 中配置 API Key")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ==========================================
# 2. 侧边栏
# ==========================================
with st.sidebar:
    st.header("📂 投喂区")
    uploaded_files = st.file_uploader("上传合同 (TXT)", type=["txt"], accept_multiple_files=True)
    if st.button("🗑️ 重置 Agent"):
        st.session_state.messages = []
        if "analysis_result" in st.session_state:
            del st.session_state["analysis_result"]
        st.rerun()

# ==========================================
# 3. 核心逻辑：感知 (Level 2)
# ==========================================
st.title("🕵️‍♂️ DeepSeek 审计智能体 (Agent Mode)")
st.caption("流程：读取合同 -> 风险量化 -> 自动决策 -> 生成邮件")

if uploaded_files and "analysis_result" not in st.session_state:
    # 1. 读取文件
    files_text = ""
    for file in uploaded_files:
        files_text += f"\n=== {file.name} ===\n{file.read().decode('utf-8')}\n"

    # 2. 调用 AI 进行结构化提取 (感知)
    with st.spinner("🧠 Agent 正在分析风险数据..."):
        json_prompt = f"""
        任务：分析合同风险。
        输出：严格的 JSON 格式，包含：
        - risk_score (0-100整数)
        - risk_level (高/中/低)
        - entity_name (对方公司名)
        - summary (风险点总结)
        
        合同内容：
        {files_text}
        """
        
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个输出 JSON 的审计算法。不要输出 Markdown 标记。"},
                    {"role": "user", "content": json_prompt}
                ],
                temperature=0.0,
                stream=False
            )
            
            # 清洗数据
            raw_content = response.choices[0].message.content.strip()
            if raw_content.startswith("```json"): raw_content = raw_content[7:]
            if raw_content.endswith("```"): raw_content = raw_content[:-3]
            
            st.session_state.analysis_result = json.loads(raw_content)
            st.rerun() # 刷新页面进入决策阶段
            
        except Exception as e:
            st.error(f"分析失败: {e}")

# ==========================================
# 4. 核心逻辑：决策与执行 (Level 3)
# ==========================================
if "analysis_result" in st.session_state:
    data = st.session_state.analysis_result
    
    # --- A. 展示感知结果 (仪表盘) ---
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("🔮 风险评分", f"{data['risk_score']} 分")
    c2.metric("💣 风险等级", data['risk_level'])
    c3.metric("🏢 对方公司", data['entity_name'])
    st.info(f"📝 风险摘要：{data['summary']}")

    # --- B. Agent 自动决策 ---
    st.divider()
    st.subheader("🤖 Agent 自动决策执行")

    # 决策逻辑
    if data['risk_score'] > 80:
        decision = "reject"
        alert_type = st.error
        decision_text = "⚠️ 风险过高，触发【拒签】流程"
        email_task = f"给 {data['entity_name']} 写一封委婉但坚定的拒签邮件。指出风险点：{data['summary']}。不需要署名。"
    else:
        decision = "approve"
        alert_type = st.success
        decision_text = "✅ 风险可控，触发【推进】流程"
        email_task = f"给法务部写一封邮件，申请推进与 {data['entity_name']} 的合同签署。备注：{data['summary']}。不需要署名。"

    # 显示决策
    alert_type(decision_text)

    # --- C. 执行 (写邮件) ---
    if "email_draft" not in st.session_state:
        with st.spinner("✍️ Agent 正在草拟邮件..."):
            email_res = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": email_task}],
                temperature=0.7
            )
            st.session_state.email_draft = email_res.choices[0].message.content
            st.rerun()

    # 展示邮件
    st.text_area("📧 自动生成的邮件草稿 (可直接复制)", value=st.session_state.email_draft, height=300)

    # 调试信息
    with st.expander("查看原始 JSON"):
        st.json(data)