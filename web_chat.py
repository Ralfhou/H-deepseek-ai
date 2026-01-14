import streamlit as st
from openai import OpenAI
import json  # 👈 必须要有这个

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(
    page_title="DeepSeek 审计仪表盘",
    page_icon="📊",
    layout="wide"  # 宽屏模式，看数据更爽
)

# ==========================================
# 2. 获取 API Key (从保险箱取)
# ==========================================
api_key = st.secrets.get("DEEPSEEK_API_KEY")
if not api_key:
    st.error("❌ 未检测到 API Key，请在 Streamlit Secrets 中配置！")
    st.stop()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

# ==========================================
# 3. 侧边栏：上传区
# ==========================================
with st.sidebar:
    st.header("📂 文件投喂")
    uploaded_files = st.file_uploader(
        "请上传合同/文档 (TXT)", 
        type=["txt"], 
        accept_multiple_files=True
    )
    
    st.divider()
    
    # 清空历史按钮
    if st.button("🗑️ 清空分析记录"):
        st.session_state.messages = []
        if "last_files" in st.session_state:
            del st.session_state["last_files"]
        st.rerun()

# 初始化 session_state
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 4. 核心逻辑：Level 2 JSON 结构化提取
# ==========================================
st.title("📊 DeepSeek 智能审计仪表盘")
st.caption("Level 2: 结构化数据提取 (JSON Mode)")

# 检测新文件
current_file_names = [f.name for f in uploaded_files] if uploaded_files else []
previous_file_names = st.session_state.get("last_files", [])

if uploaded_files and current_file_names != previous_file_names:
    st.session_state.last_files = current_file_names
    
    # 读取文件内容
    files_text = ""
    for file in uploaded_files:
        content = file.read().decode("utf-8")
        files_text += f"\n=== 文件名：{file.name} ===\n{content}\n"

    # 🧠 JSON 专用 Prompt (核心中的核心)
    system_prompt_content = f"""
    # Role
    你是一个严谨的数据提取算法。你的任务是从用户上传的文档中提取关键信息，并严格以 JSON 格式输出。

    # Context
    用户上传了以下文档内容：
    {files_text}

    # Goals
    请提取以下字段：
    1. "risk_score": 风险评分 (0-100的整数，100为最高危)
    2. "risk_level": 风险等级 (字符串：高/中/低)
    3. "entity_name": 甲方/乙方的公司名称 (如果没找到写 "未知")
    4. "summary": 一句话总结 (不超过 20 字)

    # Constraint (绝对限制)
    1. **只输出 JSON**。
    2. 不要包含 markdown 格式（如 ```json ... ```）。
    3. 不要任何开场白或结束语。
    4. 确保 JSON 格式合法。
    """

    # 构造消息历史
    st.session_state.messages = [{"role": "system", "content": system_prompt_content}]
    st.session_state.messages.append({"role": "user", "content": "开始提取数据"})

    # 直接调用 AI (Loading 转圈圈)
    with st.spinner("🤖 正在进行数据结构化提取..."):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=st.session_state.messages,
                temperature=0.1,  # 低温，保证数据严谨
                stream=False      # JSON 模式不需要流式输出
            )
            result_text = response.choices[0].message.content.strip()
            
            # 🧹 清洗数据 (防止 AI 偶尔加 markdown 符号)
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            # 🔓 解析 JSON
            data = json.loads(result_text)
            
            # 🎉 成功！存储数据到 session 以便显示
            st.session_state.analysis_result = data
            st.success("✅ 数据提取成功！")
            
        except json.JSONDecodeError:
            st.error("❌ JSON 解析失败，AI 可能说了废话。请重试。")
            st.warning(f"原始回复: {result_text}")
        except Exception as e:
            st.error(f"❌ 发生错误: {e}")

# ==========================================
# 5. 结果展示区 (Dashboard)
# ==========================================
if "analysis_result" in st.session_state:
    data = st.session_state.analysis_result
    
    # 🎨 展示漂亮的指标卡片
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🔮 风险评分", 
            value=f"{data['risk_score']} 分", 
            delta="-高危" if data['risk_score'] > 80 else "安全"
        )
    
    with col2:
        st.metric(label="💣 风险等级", value=data['risk_level'])
        
    with col3:
        st.metric(label="🏢 公司名称", value=data['entity_name'])

    st.info(f"📝 **总结**：{data['summary']}")

    # 🕵️‍♂️ 给程序员看的原始数据
    with st.expander("🔍 查看原始 JSON 数据"):
        st.json(data)