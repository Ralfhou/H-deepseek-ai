import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json
import concurrent.futures
import datetime  # 👈 核心补丁：引入时间感知

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 终极全知者 (Pro)", page_icon="🧿", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 核心大脑 (Function Calls) - 已打时效性补丁
# ==========================================

def step_1_expert_planning(query):
    """ 谋士：注入时间感知，强制搜索最新信息 """
    # 获取当前日期
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    你是一个对【最新前沿动态】极其敏感的顶级情报官。
    今天是：{today}。
    
    用户的问题是："{query}"。
    
    任务：设计 3 个【互不重叠】、【极具穿透力】的搜索关键词。
    
    ⚠️ 核心原则 (必须遵守)：
    1. **拒绝过时信息**：用户非常反感 1 年前的旧闻。如果涉及科技/金融，必须优先关注【最近 1 个月】的动态。
    2. **拒绝死板定义**：对于类似 FSD、AI 模型等话题，不要搜“什么是xx”，要搜“xx 最新评测”或“xx 实际能力”。
    3. **包含时间锚点**：搜索词里尽量包含年份（如 2025, 2026）或最新版本号（如 v13, latest）。
    
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
            # max_results 设为 5，确保抓取足够的最新文章
            res = tavily.search(query=q, search_depth="advanced", max_results=5)
            return q, res['results']
        except Exception as e:
            return q, []

    # 并行线程池
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
    1. 像法医一样剖析细节，寻找魔鬼细节。
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
    """ 最终报告：强制进行时效性辨析与反教条 """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    今天是 {today}。
    用户问题："{query}"
    
    你手头有最新的深度调查资料：
    【事实】：{analyses['facts']}
    【利益】：{analyses['interests']}
    【盲点】：{analyses['blindspots']}
    
    请写一份**极具时效性**的深度研究报告。
    
    ⚠️ 特别指令 (反幻觉补丁)：
    1. **辨析“定义”与“现实”**：如果用户的认知（如 FSD 强于 L2）与官方/法律定义（L2）有冲突，请在报告中专门分析“法律滞后于技术”的现象，不要死板地照抄定义。
    2. **数据优先**：尽量引用资料中的最新版本号（如 v12.5, v13）、最新日期。
    3. **结论犀利**：不要模棱两可，要给出基于最新事实的判断。
    
    结构建议：
    1. 🛡️ **执行摘要** (包含最新时间节点的结论)
    2. 🔍 **现状与定义之争** (专门解释“为何官方说是A，实际体验是B”)
    3. ⚔️ **各方利益博弈**
    4. ⚠️ **未来风险与盲点**
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
    st.header("🧿 全知者 (Level 9 Pro)")
    st.markdown("""
    **Pro 版特性：**
    1. **时效增强**：自动注入当前日期，拒绝旧闻。
    2. **反教条**：强制辨析“官方定义”与“实际能力”。
    3. **并行加速**：3x 并行搜索 + 3x 深度分析。
    """)
    st.info(f"📅 当前系统时间：{datetime.datetime.now().strftime('%Y-%m-%d')}")

st.title("🧿 DeepSeek Oracle (终极全知者 Pro)")
st.caption("Level 9 Pro: Real-time, Anti-Dogma, Deep Reasoning")

user_input = st.chat_input("请输入一个需要【最新】且【深度】解读的问题...")

if user_input:
    st.chat_message("user").write(user_input)
    
    with st.chat_message("assistant"):
        with st.status("🚀 全知者系统启动 (时效模式)...", expanded=True) as status:
            
            # --- Phase 1: 谋划 ---
            status.write("🧠 1. 正在制定最新情报搜集策略 (Planning)...")
            plan = step_1_expert_planning(user_input)
            st.info(f"**专家策略**：{plan['reasoning']}")
            st.json(plan['queries'])
            
            # --- Phase 2: 狩猎 ---
            status.write("🌍 2. 正在全球并行搜集最新动态 (Searching)...")
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
                analyses['facts'] = step_3_deep_analyze("核心事实与最新数据", raw_context)
                st.success("事实核查完成")
            with col2:
                st.caption("利益分析中...")
                analyses['interests'] = step_3_deep_analyze("幕后利益链与商业动机", raw_context)
                st.success("利益分析完成")
            with col3:
                st.caption("盲点扫描中...")
                analyses['blindspots'] = step_3_deep_analyze("官方定义与实际体验的脱节", raw_context)
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