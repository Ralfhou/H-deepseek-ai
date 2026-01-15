import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json

# ==========================================
# 1. 配置区
# ==========================================
st.set_page_config(page_title="Deep Research 深度研究员", page_icon="🧐", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 定义 Workflow 的各个节点 (SOP)
# ==========================================

def step_1_plan(query):
    """ 策划阶段：把大问题拆解成 3 个具体的搜索方向 """
    prompt = f"""
    你是一个专业的研究员。用户的目标是："{query}"。
    请为了彻底调研这个问题，提出 3 个【互不重叠】的具体搜索关键词（Search Queries）。
    
    必须严格输出 JSON 格式，格式如下：
    {{
        "queries": ["关键词1", "关键词2", "关键词3"]
    }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"} # 强制 JSON
    )
    return json.loads(response.choices[0].message.content)['queries']

def step_2_search(queries):
    """ 执行阶段：并行搜索所有方向 """
    aggregated_content = ""
    logs = []
    
    for q in queries:
        # 使用 Tavily 的 search 功能
        res = tavily.search(query=q, search_depth="advanced", max_results=3)
        logs.append(f"🔍 已搜索：{q} (找到 {len(res['results'])} 条资料)")
        
        for item in res['results']:
            aggregated_content += f"---资料来源：{item['url']}---\n"
            aggregated_content += f"标题：{item['title']}\n"
            aggregated_content += f"内容：{item['content']}\n\n"
            
    return aggregated_content, logs

def step_3_write(query, context):
    """ 写作阶段：基于海量资料写深度报告 """
    prompt = f"""
    你是一个资深行业分析师。请基于下方的【原始调研资料】，为用户撰写一份深度研究报告。
    
    用户课题：{query}
    
    要求：
    1. **深度优先**：不要只写表面，要挖掘数据背后的逻辑。
    2. **结构化**：使用 H2, H3 标题，列表，表格等 Markdown 格式。
    3. **引用**：在文中适当位置标注信息来源（如 [来源1]）。
    4. 字数要求：不少于 800 字。
    
    【原始调研资料】：
    {context}
    """
    # 这里用流式输出
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

# ==========================================
# 3. 页面 UI (可视化 Workflow)
# ==========================================
with st.sidebar:
    st.header("🧐 深度研究 Workflow")
    st.info("原理：拆解问题 -> 多维搜索 -> 交叉验证 -> 深度写作")
    if st.button("🗑️ 清空屏幕"):
        st.session_state.messages = []
        st.rerun()

st.title("🧐 Deep Research 深度研究员")
st.caption("Level 6: Autonomous Research Workflow")

user_input = st.chat_input("请输入一个值得深度研究的话题（例如：AI Agent 的未来商业模式）...")

if user_input:
    st.chat_message("user").write(user_input)
    
    with st.chat_message("assistant"):
        # 创建一个状态容器，让用户看到 Workflow 正在跑
        with st.status("🚀 启动深度研究工作流...", expanded=True) as status:
            
            # --- Step 1: 策划 ---
            status.write("🧠 正在进行思维拆解 (Planning)...")
            sub_queries = step_1_plan(user_input)
            status.write(f"✅ 拆解为 3 个子方向：{sub_queries}")
            
            # --- Step 2: 搜集 ---
            status.write("🌍 正在全网并行搜集资料 (Data Mining)...")
            raw_data, search_logs = step_2_search(sub_queries)
            for log in search_logs:
                status.write(log)
            status.write(f"📦 共采集到 {len(raw_data)} 字符的原始情报。")
            
            # --- Step 3: 综合 ---
            status.write("✍️ 正在进行交叉分析与写作 (Drafting)...")
            status.update(label="✅ 深度报告生成完毕！", state="complete", expanded=False)

        # 实时打印最终报告
        response_stream = step_3_write(user_input, raw_data)
        placeholder = st.empty()
        full_text = ""
        for chunk in response_stream:
            if chunk.choices[0].delta.content:
                full_text += chunk.choices[0].delta.content
                placeholder.markdown(full_text + "▌")
        placeholder.markdown(full_text)