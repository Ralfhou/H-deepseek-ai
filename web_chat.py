import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures # 用于并行加速

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 终极全知者", page_icon="🧿", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 核心大脑 (Function Calls)
# ==========================================

def step_1_expert_planning(query):
    """ 谋士：把傻瓜问题转化为 3 个专家级搜索词 """
    prompt = f"""
    你是一个顶级情报官。用户的问题是："{query}"。
    为了得到最深度的结论，我们不能只搜表面。
    请设计 3 个【互不重叠】、【极具穿透力】的搜索关键词（Query）。
    
    思路方向：
    1. 核心事实与数据 (Data)
    2. 幕后黑手与利益链 (Stakeholders)
    3. 行业内的反对声音 (Contrarian Views)
    
    输出严格的 JSON 格式：
    {{
        "queries": ["搜索词1", "搜索词2", "搜索词3"],
        "reasoning": "一句话解释为什么这么搜"
    }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def step_2_parallel_search(queries):
    """ 猎手：并行执行搜索 (速度最快) """
    aggregated_context = ""
    logs = []
    
    # 定义单个搜索任务
    def fetch_one(q):
        try:
            # 这里的 max_results 设为 4，保证资料丰富度
            res = tavily.search(query=q, search_depth="advanced", max_results=4)
            return q, res['results']
        except Exception as e:
            return q, []

    # 并行线程池 (同时发 3 个请求，不用等)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_one, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            q, results = future.result()
            logs.append(f"✅ 已抓取：{q} ({len(results)} 篇)")
            for item in results:
                aggregated_context += f"---来源：{q}---\n标题：{item['title']}\n内容：{item['content']}\n\n"
    
    return aggregated_context, logs

def step_3_deep_analyze(dimension, context):
    """ 榨汁机：单点透视分析 """
    prompt = f"""
    基于以下资料，撰写【{dimension}】的深度分析片段。
    
    资料库：
    {context}
    
    要求：
    1. 像法医一样剖析细节。
    2. 必须引用资料中的具体数据或观点。
    3. 如果资料里没有，就说“证据不足”。
    """
    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content

def step_4_final_report(query, analyses):
    """ 最终报告生成 """
    prompt = f"""
    用户问题："{query}"
    
    我们已经完成了全维度的深度调查：
    【维度1：事实核查】{analyses['facts']}
    【维度2：利益博弈】{analyses['interests']}
    【维度3：盲点揭示】{analyses['blindspots']}
    
    请以此写出一份**史诗级**的深度研究报告。
    结构：
    1. 🛡️ **执行摘要** (TL;DR)
    2. 🔍 **深层真相还原**
    3. ⚔️ **各方利益博弈**
    4. ⚠️ **关键风险与盲点**
    5. 🧠 **最终结论**
    """
    return client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

# ==========================================
# 3. 页面 UI
# ==========================================
with st.sidebar:
    st.header("🧿 全知者 (Level 9)")
    st.markdown("""
    **核心机制：**
    1. **谋划**：将问题拆解为 3 个专家视角。
    2. **狩猎**：并行抓取全网数据 (3x Tavily)。
    3. **解剖**：3 维深度压榨 (3x DeepSeek)。
    4. **重构**：合成史诗级报告。
    """)
    st.warning("⚠️ 此模式消耗较大：\n- 每次消耗 3 次搜索额度\n- 消耗约 10k+ DeepSeek Token")

st.title("🧿 DeepSeek Oracle (终极全知者)")
st.caption("Level 9: The Perfect Marriage of Search & Reasoning")

user_input = st.chat_input("请输入一个值得动用核武器的问题...")

if user_input:
    st.chat_message("user").write(user_input)
    
    with st.chat_message("assistant"):
        with st.status("🚀 全知者系统启动...", expanded=True) as status:
            
            # --- Phase 1: 谋划 ---
            status.write("🧠 1. 正在召开作战会议 (Query Planning)...")
            plan = step_1_expert_planning(user_input)
            st.info(f"**专家策略**：{plan['reasoning']}")
            st.json(plan['queries'])
            
            # --- Phase 2: 狩猎 ---
            status.write("🌍 2. 正在全球并行搜集情报 (Parallel Searching)...")
            # 这里虽然搜了3次，但为了质量是值得的。
            raw_context, search_logs = step_2_parallel_search(plan['queries'])
            for log in search_logs:
                status.write(log)
            status.write(f"📦 情报库构建完成 (共 {len(raw_context)} 字符)")
            
            # --- Phase 3: 解剖 (压榨) ---
            status.write("🔪 3. 正在进行手术刀式分析 (Deep Analysis)...")
            analyses = {}
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption("事实核查中...")
                analyses['facts'] = step_3_deep_analyze("核心事实与数据交叉验证", raw_context)
                st.success("事实核查完成")
            with col2:
                st.caption("利益分析中...")
                analyses['interests'] = step_3_deep_analyze("幕后利益链与商业动机", raw_context)
                st.success("利益分析完成")
            with col3:
                st.caption("盲点扫描中...")
                analyses['blindspots'] = step_3_deep_analyze("主流叙事的漏洞与反对声音", raw_context)
                st.success("盲点扫描完成")
            
            status.update(label="✅ 深度报告生成中...", state="running", expanded=False)

        # --- Phase 4: 终局 ---
        st.divider()
        report_stream = step_4_final_report(user_input, analyses)
        
        placeholder = st.empty()
        full_text = ""
        for chunk in report_stream:
            if chunk.choices[0].delta.content:
                full_text += chunk.choices[0].delta.content
                placeholder.markdown(full_text + "▌")
        placeholder.markdown(full_text)