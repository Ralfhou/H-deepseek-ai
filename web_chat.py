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
st.set_page_config(page_title="DeepSeek 全球前沿哨兵 (Level 14)", page_icon="🔭", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 全能文件读取器 (核心升级)
# ==========================================
def read_any_file(uploaded_file):
    """ 支持 PDF, Word, TXT, Excel, CSV """
    file_type = uploaded_file.name.split('.')[-1].lower()
    text_content = ""
    
    try:
        if file_type == 'pdf':
            pdf = PdfReader(uploaded_file)
            for page in pdf.pages:
                text_content += page.extract_text() + "\n"
                
        elif file_type in ['docx', 'doc']:
            doc = Document(uploaded_file)
            text_content = "\n".join([p.text for p in doc.paragraphs])
            
        elif file_type in ['txt', 'md']:
            text_content = uploaded_file.read().decode("utf-8")
            
        elif file_type in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            text_content = df.to_markdown(index=False) # 把表格转成 Markdown 文本
            
        elif file_type == 'csv':
            df = pd.read_csv(uploaded_file)
            text_content = df.to_markdown(index=False)
            
        else:
            return "Error: 不支持的文件格式"
            
        return text_content[:30000] # 截取前 3万字，防止 Token 爆炸
        
    except Exception as e:
        return f"读取出错: {str(e)}"

# ==========================================
# 3. 核心大脑：科技情报流
# ==========================================

def step_1_trend_planning(query, local_context=""):
    """ 
    谋士：专门针对【趋势调研】的策划
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    context_prompt = ""
    if local_context:
        context_prompt = f"【参考用户上传的内部资料】：\n{local_context[:800]}...\n请确保调研方向与上述资料有相关性或对比性。"

    prompt = f"""
    你是一个【全球前沿科技情报官】。今天是 {today}。
    用户希望调研："{query}"。
    {context_prompt}
    
    请制定 3 个【极具前瞻性】的搜索策略。
    
    要求：
    1. **全球视野**：必须包含英文搜索词（如 "State of AI 2025", "Latest LLM benchmarks"）。
    2. **信源权威**：优先关注 arXiv, TechCrunch, VentureBeat, GitHub Trending 等源头。
    3. **时效性**：必须包含 {today.split('-')[0]} 年的最新动态。
    
    输出 JSON: {{ "queries": ["英文搜索词1", "中文搜索词2", "特定领域搜索词3"], "reasoning": "策划理由" }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def step_2_global_search(queries):
    """ 猎手：全球搜索 """
    aggregated_context = ""
    logs = []
    
    def fetch_one(q):
        try:
            # max_results 设为 5，保证信息量
            res = tavily.search(query=q, search_depth="advanced", max_results=5)
            return q, res['results']
        except:
            return q, []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_one, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            q, results = future.result()
            logs.append(f"✅ 已检索：{q} ({len(results)} 条)")
            for item in results:
                aggregated_context += f"---Source: {q}---\nTitle: {item['title']}\nURL: {item['url']}\nContent: {item['content']}\n\n"
    return aggregated_context, logs

def step_3_trend_report(query, web_context, local_context=""):
    """ 主笔：撰写深度趋势研报 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    local_data = ""
    if local_context:
        local_data = f"【内部背景资料】：\n{local_context}\n---------------------\n"

    prompt = f"""
    你是《麻省理工科技评论》风格的资深编辑。今天是 {today}。
    
    用户课题："{query}"
    
    {local_data}
    
    【全球情报库】：
    {web_context}
    
    请撰写一份**深度行业趋势分析报告**。
    
    ⚠️ 写作要求：
    1. **结构化**：必须包含【执行摘要】、【核心趋势解读】(至少3点)、【关键案例/数据】、【未来展望】。
    2. **去废话**：不要写“随着AI的发展...”，直接给干货，比如“OpenAI 发布的 Sora 模型展示了...”。
    3. **引用**：在文中适当位置标注数据来源。
    4. **融合**：如果用户上传了内部资料，请对比“内部现状”与“外部趋势”的差距或机会。
    5. **排版**：使用 Markdown H1, H2, H3, Bullet points。
    """
    
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

def generate_docx(topic, content):
    """ 生成精美的 Word 研报 """
    doc = Document()
    doc.add_heading(f'全球前沿科技研报：{topic}', 0)
    doc.add_paragraph(f'生成日期：{datetime.datetime.now().strftime("%Y-%m-%d")}')
    doc.add_paragraph('Report generated by DeepSeek AI Scout')
    
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        
        if line.startswith('# '): 
            doc.add_heading(line[2:], level=1)
        elif line.startswith('## '): 
            doc.add_heading(line[3:], level=2)
        elif line.startswith('### '): 
            doc.add_heading(line[4:], level=3)
        elif line.startswith('- ') or line.startswith('* '): 
            doc.add_paragraph(line[2:], style='List Bullet')
        elif line.startswith('1. '): 
            doc.add_paragraph(line[3:], style='List Number')
        else: 
            doc.add_paragraph(line)
            
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# ==========================================
# 4. 页面 UI
# ==========================================
with st.sidebar:
    st.header("🔭 哨兵控制台")
    st.markdown("支持上传：PDF, Word, TXT, Excel")
    
    uploaded_file = st.file_uploader("📂 投喂背景资料 (可选)", type=["pdf", "docx", "txt", "md", "xlsx", "csv"])
    local_text = ""
    
    if uploaded_file:
        with st.spinner("正在解析文件内容..."):
            local_text = read_any_file(uploaded_file)
        if local_text.startswith("Error"):
            st.error(local_text)
        else:
            st.success(f"✅ 已提取 {len(local_text)} 字符")
            with st.expander("查看提取内容"):
                st.text(local_text[:800] + "...")

st.title("🔭 DeepSeek 全球前沿科技哨兵")
st.caption("Level 14: Global AI Trend Research & Reporting")

user_input = st.chat_input("请输入调研方向 (例如：2026年 AI Agent 在金融领域的应用趋势)...")

if user_input:
    st.chat_message("user").write(user_input)
    
    full_report = ""
    
    with st.chat_message("assistant"):
        with st.status("🚀 启动全球侦察任务...", expanded=True) as status:
            
            # Step 1: 策划
            status.write("🧠 1. 制定搜索策略 (Global Planning)...")
            plan = step_1_trend_planning(user_input, local_text)
            st.write(f"👉 策略：{plan['reasoning']}")
            st.json(plan['queries'])
            
            # Step 2: 搜索
            status.write("🌍 2. 检索全球情报 (Tavily Advanced)...")
            web_context, logs = step_2_global_search(plan['queries'])
            for log in logs: status.write(log)
            
            # Step 3: 撰写
            status.update(label="✍️ 正在撰写深度研报...", state="running", expanded=False)
            
        st.subheader(f"📄 {user_input} - 深度趋势报告")
        stream = step_3_trend_report(user_input, web_context, local_text)
        
        placeholder = st.empty()
        for chunk in stream:
            if chunk.choices[0].delta.content:
                c = chunk.choices[0].delta.content
                full_report += c
                placeholder.markdown(full_report + "▌")
        placeholder.markdown(full_report)
        
        st.divider()
        
        # 导出 Word
        docx_file = generate_docx(user_input, full_report)
        st.download_button(
            label="📥 下载 Word 研报 (.docx)",
            data=docx_file,
            file_name=f"{user_input}_趋势研报.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )