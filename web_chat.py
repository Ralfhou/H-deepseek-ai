import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures
import datetime
from docx import Document
from io import BytesIO
from pypdf import PdfReader
from pptx import Presentation # 👈 新增：PPT 处理库
from pptx.util import Inches, Pt # 👈 新增：尺寸单位

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 全能办公助手 (Level 12)", page_icon="📊", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 工具函数：文件读取
# ==========================================
def read_pdf(file):
    try:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
        return text[:50000]
    except Exception as e:
        return f"读取失败: {e}"

# ==========================================
# 3. 核心大脑 (Level 11 + PPT 逻辑)
# ==========================================

def step_1_expert_planning(query, local_context=""):
    """ 谋士：策划 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    context_instruction = ""
    if local_context:
        context_instruction = f"【参考内部资料】：{local_context[:500]}..."
        
    prompt = f"""
    今天是：{today}。用户问题："{query}"。
    {context_instruction}
    请设计 3 个【互不重叠】的搜索关键词。
    输出 JSON: {{ "queries": ["词1", "词2", "词3"], "reasoning": "理由" }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def step_2_parallel_search(queries):
    """ 猎手：搜索 """
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
    """ 榨汁机：分析 """
    local_prompt = f"【内部资料】{local_context}" if local_context else ""
    prompt = f"""
    请撰写【{dimension}】的深度分析。
    {local_prompt}
    【全网资料】：{web_context}
    要求：深度对比，引用数据。
    """
    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content

def step_4_final_report(query, analyses):
    """ 报告生成 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    今天是 {today}。用户问题："{query}"
    资料：【事实】{analyses['facts']} 【利益】{analyses['interests']} 【盲点】{analyses['blindspots']}
    请写一份 Markdown 格式的深度研报。包含：核心摘要、深度分析、风险、结论。
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

def step_5_generate_ppt_content(topic, report_text):
    """ 
    新增步骤：PPT 结构化大师 
    将长篇报告转化为 PPT 的 JSON 结构
    """
    prompt = f"""
    你是一个 PPT 制作专家。请将下面的【深度研报】转化为一份 6-8 页的 PPT 大纲。
    
    研报主题：{topic}
    研报内容：
    {report_text[:10000]}
    
    要求：
    1. 第一页必须是封面（标题+副标题）。
    2. 每一页包含：Title（标题）, Points（3-5个简短的要点）。
    3. 最后一页是“谢谢”。
    
    输出严格的 JSON 格式：
    {{
        "slides": [
            {{ "layout": "title", "title": "主标题", "subtitle": "副标题/汇报人" }},
            {{ "layout": "content", "title": "目录/摘要", "points": ["要点1", "要点2"] }},
            ...
        ]
    }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ==========================================
# 4. 导出功能：Word & PPT
# ==========================================
def generate_docx(topic, content):
    """ 生成 Word """
    doc = Document()
    doc.add_heading(f'{topic}', 0)
    for line in content.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], level=1)
        elif line.startswith('## '): doc.add_heading(line[3:], level=2)
        elif line.startswith('- ') or line.startswith('* '): doc.add_paragraph(line[2:], style='List Bullet')
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

def generate_pptx_file(ppt_data):
    """ 生成 PPT 文件 """
    prs = Presentation()
    
    for slide_data in ppt_data['slides']:
        if slide_data['layout'] == 'title':
            # 封面页
            slide_layout = prs.slide_layouts[0] 
            slide = prs.slides.add_slide(slide_layout)
            slide.shapes.title.text = slide_data.get('title', '')
            if 'subtitle' in slide_data:
                slide.placeholders[1].text = slide_data['subtitle']
                
        else:
            # 内容页
            slide_layout = prs.slide_layouts[1] 
            slide = prs.slides.add_slide(slide_layout)
            slide.shapes.title.text = slide_data.get('title', '')
            
            # 添加文本框
            body_shape = slide.placeholders[1]
            tf = body_shape.text_frame
            
            points = slide_data.get('points', [])
            if points:
                tf.text = points[0] # 第一行
                for p in points[1:]:
                    p_new = tf.add_paragraph()
                    p_new.text = p
                    p_new.level = 0
                    
    bio = BytesIO()
    prs.save(bio)
    bio.seek(0)
    return bio

# ==========================================
# 5. 页面 UI
# ==========================================
with st.sidebar:
    st.header("📊 Level 12: PPT Master")
    uploaded_file = st.file_uploader("📄 上传参考资料 (PDF)", type=["pdf"])
    local_text = ""
    if uploaded_file:
        local_text = read_pdf(uploaded_file)
        st.success(f"已读取 {len(local_text)} 字")

st.title("📊 DeepSeek 全能办公助手")
st.caption("Level 12: Search + Analyze + Word Report + PPT Slides")

user_input = st.chat_input("请输入主题（例如：2026年 AI 行业发展趋势）...")

if user_input:
    st.chat_message("user").write(user_input)
    full_report_text = ""
    
    with st.chat_message("assistant"):
        with st.status("🚀 全自动办公流启动...", expanded=True) as status:
            # 1. 策划
            status.write("🧠 1. 正在策划...")
            plan = step_1_expert_planning(user_input, local_text)
            
            # 2. 搜索
            status.write("🌍 2. 全网搜集中...")
            raw_context, _ = step_2_parallel_search(plan['queries'])
            
            # 3. 分析
            status.write("🔪 3. 深度分析中...")
            analyses = {
                'facts': step_3_deep_analyze("核心事实", raw_context, local_text),
                'interests': step_3_deep_analyze("利益博弈", raw_context, local_text),
                'blindspots': step_3_deep_analyze("未来趋势", raw_context, local_text)
            }
            status.update(label="✅ 分析完成，正在撰写报告...", state="running")
            
        # 4. 生成 Word 报告 (流式显示)
        st.subheader("📄 深度研报预览")
        report_stream = step_4_final_report(user_input, analyses)
        placeholder = st.empty()
        for chunk in report_stream:
            if chunk.choices[0].delta.content:
                t = chunk.choices[0].delta.content
                full_report_text += t
                placeholder.markdown(full_report_text + "▌")
        placeholder.markdown(full_report_text)
        
        # 5. 生成 PPT 逻辑 (幕后进行)
        with st.spinner("正在将研报转化为 PPT 大纲..."):
            ppt_structure = step_5_generate_ppt_content(user_input, full_report_text)
        
        st.divider()
        st.success("🎉 全套文档制作完成！")
        
        # 6. 下载区 (双按钮)
        col1, col2 = st.columns(2)
        with col1:
            docx_file = generate_docx(user_input, full_report_text)
            st.download_button("📥 下载 Word 详版 (.docx)", docx_file, 
                             file_name=f"{user_input}_研报.docx")
        with col2:
            ppt_file = generate_pptx_file(ppt_structure)
            st.download_button("📊 下载 PPT 演示稿 (.pptx)", ppt_file, 
                             file_name=f"{user_input}_演示.pptx")
            
        # 可视化展示一下 PPT 大纲
        with st.expander("👀 查看生成的 PPT 大纲"):
            st.json(ppt_structure)