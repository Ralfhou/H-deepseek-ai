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
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 智能编辑部 (Level 16)", page_icon="🕵️", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# 初始化 Session State
if "messages" not in st.session_state: st.session_state.messages = []
if "workflow_logs" not in st.session_state: st.session_state.workflow_logs = []

# ==========================================
# 2. 工具函数
# ==========================================
def read_any_file(uploaded_file):
    """ 读取文件内容 """
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
        return text_content[:30000]
    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================
# 3. 多智能体角色 (Agents)
# ==========================================

# --- Agent A: 策划 (Planner) ---
def agent_planner(query, local_context=""):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    你是一个【主编策划】。今天是 {today}。
    用户选题："{query}"。
    内部资料片段：{local_context[:500]}
    
    请制定 3 个搜索关键词，确保覆盖最新的行业动态和深度数据。
    输出 JSON: {{ "queries": ["词1", "词2", "词3"] }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- Agent B: 猎手 (Hunter) ---
def agent_searcher(queries):
    context = ""
    def fetch(q):
        try:
            return tavily.search(query=q, search_depth="advanced", max_results=3)['results']
        except: return []
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            for item in future.result():
                context += f"Source: {item['title']}\nContent: {item['content']}\n\n"
    return context

# --- Agent C: 初稿主笔 (Writer) ---
def agent_writer(query, context, local_data):
    prompt = f"""
    你是一个【资深撰稿人】。
    用户选题："{query}"
    资料库：{context}
    内部资料：{local_data}
    
    请写一份深度研报的【初稿】。
    要求：逻辑清晰，数据详实，Markdown 格式。
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- Agent D: 审稿人 (Critic) [核心新增!] ---
def agent_critic(query, draft):
    prompt = f"""
    你是一个【毒舌主编/审稿人】。
    用户选题："{query}"
    
    这是下属写的初稿：
    {draft[:10000]}
    
    请用批判性的眼光审查这份初稿：
    1. 有没有逻辑漏洞？
    2. 是否缺少关键数据支持？
    3. 观点是否过于平庸？
    
    请给出 3 条具体的【修改建议】（不要重写，只给建议）。
    输出格式：
    1. 建议一...
    2. 建议二...
    3. 建议三...
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- Agent E: 终稿精修 (Editor) [核心新增!] ---
def agent_editor(query, draft, critique):
    prompt = f"""
    你是一个【最终把关人】。
    初稿：
    {draft[:10000]}
    
    主编的修改建议：
    {critique}
    
    请根据建议，对初稿进行【重写和润色】，输出最终的完美版本。
    直接输出最终内容，不要罗嗦。
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

def generate_docx(content):
    doc = Document()
    doc.add_heading('DeepSeek 深度研报 (精修版)', 0)
    for line in content.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], level=1)
        elif line.startswith('## '): doc.add_heading(line[3:], level=2)
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# ==========================================
# 4. 页面 UI
# ==========================================
with st.sidebar:
    st.header("🕵️ 编辑部控制台")
    uploaded_file = st.file_uploader("📂 资料投喂", type=["pdf", "docx", "txt"])
    local_text = ""
    if uploaded_file:
        local_text = read_any_file(uploaded_file)
        st.success("资料已就位")

    if st.button("🗑️ 清空工作流"):
        st.session_state.messages = []
        st.rerun()

st.title("🕵️ DeepSeek 智能编辑部 (Multi-Agent)")
st.caption("Level 16: Planner -> Searcher -> Writer -> Critic -> Editor")

# 显示历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("请输入调研选题..."):
    
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        # 使用 st.status 展示多智能体协作过程
        with st.status("🚀 编辑部全员集结，开始工作...", expanded=True) as status:
            
            # 1. 策划
            status.write("🧠 [策划] 正在制定搜索方案...")
            plan = agent_planner(user_input, local_text)
            st.json(plan['queries'])
            
            # 2. 搜索
            status.write("🌍 [探员] 正在全球搜集情报...")
            web_context = agent_searcher(plan['queries'])
            
            # 3. 初稿
            status.write("✍️ [主笔] 正在撰写初稿 (Draft V1)...")
            draft_v1 = agent_writer(user_input, web_context, local_text)
            with st.expander("查看初稿 (Draft V1)"):
                st.markdown(draft_v1)
            
            # 4. 审稿 (亮点步骤!)
            status.write("⚖️ [主编] 正在进行严厉审稿...")
            critique = agent_critic(user_input, draft_v1)
            st.info(f"**主编意见**：\n{critique}")
            
            # 5. 精修
            status.update(label="✨ [终审] 正在根据意见重写最终版...", state="running")
            final_stream = agent_editor(user_input, draft_v1, critique)
            
            # 流式输出最终版
            full_response = ""
            placeholder = st.empty()
            for chunk in final_stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
            
            status.update(label="✅ 工作流执行完毕", state="complete", expanded=False)

    # 保存记忆
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # 下载按钮
    st.download_button("📥 下载精修研报", generate_docx(full_response), "final_report.docx")