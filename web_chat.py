import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures
import datetime
from docx import Document
from io import BytesIO
from pypdf import PdfReader
import pandas as pd

# ==========================================
# 1. 基础配置 & 记忆初始化
# ==========================================
st.set_page_config(page_title="DeepSeek 对话式研报助手 (Level 15)", page_icon="💬", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# --- 核心：初始化聊天记录 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 核心：初始化上下文记忆 (用于判断是否已生成过报告) ---
if "has_report" not in st.session_state:
    st.session_state.has_report = False

# ==========================================
# 2. 工具函数 (保留之前的强力功能)
# ==========================================
def read_any_file(uploaded_file):
    """ 全能文件读取 """
    file_type = uploaded_file.name.split('.')[-1].lower()
    text_content = ""
    try:
        if file_type == 'pdf':
            pdf = PdfReader(uploaded_file)
            for page in pdf.pages: text_content += page.extract_text() + "\n"
        elif file_type in ['docx', 'doc']:
            doc = Document(uploaded_file)
            text_content = "\n".join([p.text for p in doc.paragraphs])
        elif file_type in ['txt', 'md']:
            text_content = uploaded_file.read().decode("utf-8")
        elif file_type in ['xlsx', 'xls', 'csv']:
            df = pd.read_excel(uploaded_file) if 'xls' in file_type else pd.read_csv(uploaded_file)
            text_content = df.to_markdown(index=False)
        return text_content[:30000]
    except Exception as e:
        return f"Error: {str(e)}"

def step_1_trend_planning(query, local_context=""):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    context_prompt = f"【参考内部资料】：\n{local_context[:800]}..." if local_context else ""
    prompt = f"""
    你是情报官。今天是 {today}。用户调研："{query}"。{context_prompt}
    请制定 3 个搜索关键词（包含中英文、前沿源头）。
    输出 JSON: {{ "queries": ["词1", "词2", "词3"], "reasoning": "理由" }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def step_2_global_search(queries):
    aggregated_context = ""
    def fetch_one(q):
        try:
            res = tavily.search(query=q, search_depth="advanced", max_results=4)
            return res['results']
        except: return []
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_one, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            results = future.result()
            for item in results:
                aggregated_context += f"---Source---\nTitle: {item['title']}\nContent: {item['content']}\n\n"
    return aggregated_context

def step_3_trend_report(query, web_context, local_context=""):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    local_data = f"【内部资料】：\n{local_context}\n" if local_context else ""
    prompt = f"""
    你是资深分析师。今天是 {today}。
    用户课题："{query}"
    {local_data}
    【情报库】：{web_context}
    
    请撰写深度趋势研报。Markdown格式。
    结构：摘要、核心趋势、案例、展望。
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

def generate_docx(content):
    doc = Document()
    doc.add_heading('DeepSeek 研报', 0)
    for line in content.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], level=1)
        elif line.startswith('## '): doc.add_heading(line[3:], level=2)
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# ==========================================
# 3. 页面 UI & 交互逻辑
# ==========================================
with st.sidebar:
    st.header("💬 对话控制台")
    uploaded_file = st.file_uploader("📂 投喂背景资料", type=["pdf", "docx", "txt", "xlsx"])
    local_text = ""
    if uploaded_file:
        local_text = read_any_file(uploaded_file)
        st.success(f"已读取 {len(local_text)} 字")

    # 新增：清空对话按钮
    if st.button("🗑️ 开启新话题 (清空记忆)"):
        st.session_state.messages = []
        st.session_state.has_report = False
        st.rerun()

st.title("💬 DeepSeek 对话式研报助手")
st.caption("Level 15: Chat with your Research")

# --- A. 展示历史聊天记录 ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- B. 处理新输入 ---
if user_input := st.chat_input("请输入调研方向，或者针对已有报告进行追问..."):
    
    # 1. 显示用户输入
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. 生成回答 (分两种模式)
    with st.chat_message("assistant"):
        
        # 模式一：如果还没有报告，先做【深度调研】
# 模式一：如果还没有报告，先做【深度调研】
        if not st.session_state.has_report:
            with st.status("🚀 正在进行首次深度调研...", expanded=True) as status:  # ✅ 改成这样
                
                # Step 1: 策划
                status.write("🧠 策划搜索方案...")
                plan = step_1_trend_planning(user_input, local_text)
                
                # Step 2: 搜索
                status.write(f"🌍 全网检索: {plan['queries']}...")
                web_context = step_2_global_search(plan['queries'])
                
                # Step 3: 写作
                status.update(label="✍️ 正在生成深度研报...", state="running")
                report_stream = step_3_trend_report(user_input, web_context, local_text)
            
            # 流式输出 (注意缩进要跳出 with st.status 的层级)
            full_response = ""
            placeholder = st.empty()
            for chunk in report_stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
            
            # 标记状态：已有报告
            st.session_state.has_report = True
            
            # 提供下载
            docx = generate_docx(full_response)
            st.download_button("📥 下载研报 (.docx)", docx, "report.docx")

        # 模式二：如果已有报告，进行【对话追问】
        else:
            # 直接调用 DeepSeek 进行聊天
            # 我们把历史记录发给它，它就能看到之前的报告
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的研报助手。请基于上下文中的报告内容回答用户问题。如果用户问了新领域，建议他们点击清空按钮。"}
                ] + st.session_state.messages, # 包含所有历史
                stream=True
            )
            
            full_response = ""
            placeholder = st.empty()
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

    # 3. 保存 AI 的回复到记忆
    st.session_state.messages.append({"role": "assistant", "content": full_response})