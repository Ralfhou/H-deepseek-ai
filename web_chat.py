import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures
import datetime
from docx import Document  # 👈 新增：处理 Word 文档
from io import BytesIO     # 👈 新增：在内存中处理文件

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 研报生成器 (Level 10)", page_icon="🖨️", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 核心大脑 (Level 9 的逻辑)
# ==========================================

def step_1_expert_planning(query):
    """ 谋士：注入时间感知 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    今天是：{today}。用户问题："{query}"。
    请设计 3 个【互不重叠】的搜索关键词。
    要求：
    1. 关注最新动态（包含年份或版本号）。
    2. 拒绝死板定义。
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
            res = tavily.search(query=q, search_depth="advanced", max_results=5)
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

def step_3_deep_analyze(dimension, context):
    """ 榨汁机：分析 """
    prompt = f"""
    基于资料库，撰写【{dimension}】的深度分析。
    资料库：{context}
    要求：引用具体数据，分析透彻。
    """
    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content

def step_4_final_report(query, analyses):
    """ 最终报告生成 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    今天是 {today}。用户问题："{query}"
    资料：【事实】{analyses['facts']} 【利益】{analyses['interests']} 【盲点】{analyses['blindspots']}
    
    请写一份**结构化**的深度研报。
    格式要求：
    - 不要使用 ```markdown 标记，直接输出内容。
    - 使用 # 一级标题, ## 二级标题 等标准格式。
    - 包含：1. 核心摘要 2. 深度分析 3. 风险提示 4. 结论。
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

# ==========================================
# 3. 新增功能：打印机 (生成 Word)
# ==========================================
def generate_docx(topic, content):
    """ 将 Markdown 文本转换为 Word 文档 """
    doc = Document()
    
    # 添加标题
    doc.add_heading(f'深度研报：{topic}', 0)
    doc.add_paragraph(f'生成时间：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}')
    
    # 简单处理 Markdown (将 # 转换为 Word 标题)
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            doc.add_heading(line[2:], level=1)
        elif line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('### '):
            doc.add_heading(line[4:], level=3)
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(line[2:], style='List Bullet')
        else:
            if line: # 跳过空行
                doc.add_paragraph(line)
                
    # 保存到内存 (不存硬盘，适合云端)
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# ==========================================
# 4. 页面 UI
# ==========================================
with st.sidebar:
    st.header("🖨️ Level 10: Publisher")
    st.markdown("现在，你的 Agent 可以直接**交付结果**了。")

st.title("🖨️ DeepSeek 深度研报生成器")
st.caption("Level 10: Auto-generate & Download Word Reports")

user_input = st.chat_input("请输入调研主题...")

if user_input:
    st.chat_message("user").write(user_input)
    
    # 初始化完整报告内容的容器
    full_report_text = ""
    
    with st.chat_message("assistant"):
        with st.status("🚀 正在生成交付级报告...", expanded=True) as status:
            # Phase 1
            status.write("🧠 1. 策划中...")
            plan = step_1_expert_planning(user_input)
            
            # Phase 2
            status.write("🌍 2. 全网搜集中...")
            raw_context, _ = step_2_parallel_search(plan['queries'])
            
            # Phase 3
            status.write("🔪 3. 深度分析中...")
            analyses = {
                'facts': step_3_deep_analyze("事实与数据", raw_context),
                'interests': step_3_deep_analyze("利益博弈", raw_context),
                'blindspots': step_3_deep_analyze("盲点与争议", raw_context)
            }
            
            status.update(label="✅ 分析完成，正在撰写...", state="running")
            
        # Phase 4: 流式输出 + 记录全文
        st.subheader(f"📄 {user_input} - 研报预览")
        report_stream = step_4_final_report(user_input, analyses)
        
        placeholder = st.empty()
        for chunk in report_stream:
            if chunk.choices[0].delta.content:
                text_chunk = chunk.choices[0].delta.content
                full_report_text += text_chunk
                placeholder.markdown(full_report_text + "▌")
        placeholder.markdown(full_report_text)
        
        # Phase 5: 提供下载按钮
        st.divider()
        st.success("🎉 报告已生成！")
        
        # 调用 Word 生成函数
        docx_file = generate_docx(user_input, full_report_text)
        
        st.download_button(
            label="📥 下载 Word 格式研报 (.docx)",
            data=docx_file,
            file_name=f"{user_input}_深度研报.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )