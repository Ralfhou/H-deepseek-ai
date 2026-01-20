import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures
import datetime
from docx import Document
from io import BytesIO
from pypdf import PdfReader  # 👈 新增：PDF 阅读能力

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 混合情报专家 (Level 11)", page_icon="📂", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 工具函数：读取上传的文件
# ==========================================
def read_pdf(file):
    """ 从 PDF 中提取文本 """
    try:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
        return text[:50000] # 限制长度防止 Token 爆炸 (DeepSeek 支持 64k 但我们留点余地)
    except Exception as e:
        return f"读取失败: {e}"

# ==========================================
# 3. 核心大脑 (升级版)
# ==========================================

def step_1_expert_planning(query, local_context=""):
    """ 谋士：结合本地资料进行策划 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 如果有本地资料，Prompt 会有所不同
    context_instruction = ""
    if local_context:
        context_instruction = f"""
        【重要】用户上传了一份内部资料（摘要）：
        "{local_context[:500]}..."
        请根据这份资料的内容，针对性地去网上挖掘补充信息或竞争对手信息。
        """

    prompt = f"""
    今天是：{today}。用户问题："{query}"。
    {context_instruction}
    
    请设计 3 个【互不重叠】的搜索关键词。
    要求：
    1. 必须结合用户上传的资料（如果有）。
    2. 关注最新动态。
    输出 JSON: {{ "queries": ["词1", "词2", "词3"], "reasoning": "理由" }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def step_2_parallel_search(queries):
    """ 猎手：并行搜索 """
    aggregated_context = ""
    logs = []
    
    def fetch_one(q):
        try:
            res = tavily.search(query=q, search_depth="advanced", max_results=4)
            return q, res['results']
        except:
            return q, []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_one, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            q, results = future.result()
            logs.append(f"✅ 已抓取：{q} ({len(results)} 篇)")
            for item in results:
                aggregated_context += f"---来源：{q}---\n标题：{item['title']}\n内容：{item['content']}\n\n"
    return aggregated_context, logs

def step_3_deep_analyze(dimension, web_context, local_context=""):
    """ 榨汁机：混合分析 """
    # 注入本地知识
    local_data_prompt = ""
    if local_context:
        local_data_prompt = f"""
        【内部参考资料】：
        {local_context}
        ----------------------------------
        """
        
    prompt = f"""
    请撰写【{dimension}】的深度分析。
    
    {local_data_prompt}
    
    【全网搜索资料】：
    {web_context}
    
    要求：
    1. 将“内部资料”与“外部搜索结果”进行对比、印证或补充。
    2. 引用具体数据。
    """
    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content

def step_4_final_report(query, analyses):
    """ 最终报告 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    今天是 {today}。用户问题："{query}"
    资料：【事实】{analyses['facts']} 【利益】{analyses['interests']} 【盲点】{analyses['blindspots']}
    
    请写一份深度混合研报。
    格式要求：使用标准 Markdown (#, ##)，包含核心摘要、深度对比分析、结论。
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

def generate_docx(topic, content):
    """ 生成 Word """
    doc = Document()
    doc.add_heading(f'深度混合研报：{topic}', 0)
    doc.add_paragraph(f'生成时间：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}')
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# '): doc.add_heading(line[2:], level=1)
        elif line.startswith('## '): doc.add_heading(line[3:], level=2)
        elif line.startswith('### '): doc.add_heading(line[4:], level=3)
        elif line.startswith('- ') or line.startswith('* '): doc.add_paragraph(line[2:], style='List Bullet')
        else: 
            if line: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# ==========================================
# 4. 页面 UI
# ==========================================
with st.sidebar:
    st.header("📂 Level 11: Hybrid Analyst")
    
    # 文件上传区
    uploaded_file = st.file_uploader("📄 投喂内部资料 (可选 PDF)", type=["pdf"])
    local_text = ""
    
    if uploaded_file:
        with st.spinner("正在阅读文件..."):
            local_text = read_pdf(uploaded_file)
        st.success(f"已提取 {len(local_text)} 字的内部资料")
        with st.expander("查看文件内容"):
            st.text(local_text[:1000] + "...")

st.title("📂 DeepSeek 混合情报专家")
st.caption("Level 11: RAG (Retrieval-Augmented Generation) + Web Search")

user_input = st.chat_input("请输入调研主题（可结合左侧上传的文件）...")

if user_input:
    st.chat_message("user").write(user_input)
    
    full_report_text = ""
    
    with st.chat_message("assistant"):
        with st.status("🚀 启动混合分析引擎...", expanded=True) as status:
            
            # Phase 1
            status.write("🧠 1. 结合内外部资料策划中...")
            plan = step_1_expert_planning(user_input, local_text)
            st.json(plan) # 展示一下它想搜什么，看看它有没有理解你的文件
            
            # Phase 2
            status.write("🌍 2. 全网搜集中...")
            raw_context, _ = step_2_parallel_search(plan['queries'])
            
            # Phase 3
            status.write("🔪 3. 深度混合分析中...")
            analyses = {
                'facts': step_3_deep_analyze("事实与数据对比", raw_context, local_text),
                'interests': step_3_deep_analyze("利益博弈与竞争", raw_context, local_text),
                'blindspots': step_3_deep_analyze("盲点与机会", raw_context, local_text)
            }
            
            status.update(label="✅ 分析完成，正在撰写...", state="running")
            
        # Phase 4
        st.subheader(f"📄 {user_input} - 混合研报预览")
        report_stream = step_4_final_report(user_input, analyses)
        
        placeholder = st.empty()
        for chunk in report_stream:
            if chunk.choices[0].delta.content:
                text_chunk = chunk.choices[0].delta.content
                full_report_text += text_chunk
                placeholder.markdown(full_report_text + "▌")
        placeholder.markdown(full_report_text)
        
        # Phase 5
        st.divider()
        docx_file = generate_docx(user_input, full_report_text)
        st.download_button(
            label="📥 下载混合研报 (.docx)",
            data=docx_file,
            file_name=f"{user_input}_混合研报.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )