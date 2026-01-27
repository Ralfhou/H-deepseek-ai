import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures
import datetime
from docx import Document
from io import BytesIO
from pypdf import PdfReader

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 导演剪辑版 (Level 17)", page_icon="🎬", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# --- 核心状态管理 ---
if "messages" not in st.session_state: st.session_state.messages = []
if "current_report" not in st.session_state: st.session_state.current_report = "" # 存储当前版本的报告
if "web_context" not in st.session_state: st.session_state.web_context = "" # 存储已搜集的情报

# ==========================================
# 2. 智能体定义 (Agents)
# ==========================================

# --- Agent A: 策划 (Planner) ---
def agent_planner(query, local_context=""):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    你是一个【主编策划】。今天是 {today}。
    用户选题："{query}"。
    内部资料：{local_context[:500]}
    
    请制定 3 个搜索关键词，确保覆盖最新的行业动态。
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
    new_context = ""
    def fetch(q):
        try:
            return tavily.search(query=q, search_depth="advanced", max_results=3)['results']
        except: return []
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            for item in future.result():
                new_context += f"Source: {item['title']}\nContent: {item['content']}\n\n"
    return new_context

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

# --- Agent D: 补救策划 (Replanner) [Level 17 新增] ---
def agent_replanner(feedback, current_report):
    """ 判断用户的反馈是否需要联网搜索 """
    prompt = f"""
    用户对报告提出了修改意见："{feedback}"
    当前报告摘要：{current_report[:500]}...
    
    请判断：为了满足该意见，是否需要【去网上搜索新信息】？
    - 如果是（例如“补充xx的数据”），请生成搜索词。
    - 如果否（例如“改短一点”、“换个语气”），请返回空列表。
    
    输出 JSON: {{ "needs_search": true/false, "queries": ["词1", "词2"] }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- Agent E: 精修/重写 (Editor) ---
def agent_editor(query, draft, instructions, new_context=""):
    prompt = f"""
    你是一个【最终把关人】。
    
    【当前版本】：
    {draft}
    
    【修改指令】：
    {instructions}
    
    【新补充的搜索资料】(如果有)：
    {new_context}
    
    请严格根据指令，对当前版本进行【重写/修订】。
    如果有了新资料，请融合进去。
    直接输出最终内容。
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

def generate_docx(content):
    doc = Document()
    doc.add_heading('DeepSeek 深度研报', 0)
    for line in content.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], level=1)
        elif line.startswith('## '): doc.add_heading(line[3:], level=2)
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def read_any_file(uploaded_file):
    # (保持之前的逻辑不变)
    try:
        if uploaded_file.name.endswith('.pdf'):
            pdf = PdfReader(uploaded_file)
            return "".join([p.extract_text() for p in pdf.pages])[:30000]
        else:
            return uploaded_file.read().decode("utf-8")[:30000]
    except: return ""

# ==========================================
# 3. 页面 UI
# ==========================================
with st.sidebar:
    st.header("🎬 导演控制台")
    uploaded_file = st.file_uploader("📂 资料投喂", type=["pdf", "txt"])
    local_text = ""
    if uploaded_file: local_text = read_any_file(uploaded_file)

    if st.button("🗑️ 清空重来"):
        st.session_state.current_report = ""
        st.session_state.web_context = ""
        st.session_state.messages = []
        st.rerun()

st.title("🎬 DeepSeek 智能编辑部 (人机协同版)")
st.caption("Level 17: User Feedback Loop & Auto-Replanning")

# 展示历史对话
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 主逻辑：如果还没有报告，显示主输入框 ---
if not st.session_state.current_report:
    if user_input := st.chat_input("请输入初始选题..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.write(user_input)

        with st.chat_message("assistant"):
            with st.status("🚀 第一次全流程制作中...", expanded=True) as status:
                # 1. 策划
                status.write("🧠 [策划] 制定初始方案...")
                plan = agent_planner(user_input, local_text)
                
                # 2. 搜索
                status.write("🌍 [猎手] 全网搜索...")
                web_ctx = agent_searcher(plan['queries'])
                st.session_state.web_context = web_ctx # 保存到记忆
                
                # 3. 写作
                status.write("✍️ [主笔] 撰写初稿...")
                draft = agent_writer(user_input, web_ctx, local_text)
                
                status.update(label="✅ 初稿完成！请在下方提出修改意见", state="complete")

            # 显示初稿
            st.markdown(draft)
            st.session_state.messages.append({"role": "assistant", "content": draft})
            st.session_state.current_report = draft
            st.rerun() # 强制刷新，让界面进入“修改模式”

# --- 修改逻辑：如果已有报告，显示“修改意见”输入框 ---
else:
    # 下载按钮常驻
    st.download_button("📥 下载当前版本 (.docx)", generate_docx(st.session_state.current_report), "report.docx")
    
    # 修改意见输入框 (注意：这里不用 st.chat_input，改用 form 以便更清晰)
    with st.form("revision_form"):
        feedback = st.text_area("✍️ 导演指示 (对报告哪里不满意？)", placeholder="例如：给我在第二段补充一下 OpenAI 的最新数据...")
        submitted = st.form_submit_button("🚀 提交修改指令")
        
    if submitted and feedback:
        # 显示用户的修改指令
        st.session_state.messages.append({"role": "user", "content": f"【修改指令】{feedback}"})
        with st.chat_message("user"): st.write(f"【修改指令】{feedback}")
        
        with st.chat_message("assistant"):
            with st.status("🔧 正在执行修改工作流...", expanded=True) as status:
                
                # 1. 决策：是否需要补搜？
                status.write("🤔 [决策] 正在判断是否需要补搜资料...")
                replan_result = agent_replanner(feedback, st.session_state.current_report)
                
                new_info = ""
                if replan_result['needs_search']:
                    status.write(f"🌍 [猎手] 发现信息缺口，正在补搜：{replan_result['queries']}")
                    new_info = agent_searcher(replan_result['queries'])
                    st.session_state.web_context += f"\n\n=== 补搜资料 ===\n{new_info}" # 追加到记忆
                else:
                    status.write("👌 [决策] 无需补搜，直接进行文本调整。")
                
                # 2. 精修
                status.write("✨ [精修] 正在根据指示重写...")
                # 注意：我们把 feedback 当作 instructions 传进去
                stream = agent_editor(feedback, st.session_state.current_report, feedback, new_info)
                
                full_response = ""
                placeholder = st.empty()
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
                
                # 更新状态
                st.session_state.current_report = full_response
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                status.update(label="✅ 修改完成", state="complete")
        
        st.rerun()