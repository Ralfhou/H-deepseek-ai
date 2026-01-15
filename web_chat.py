import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import json

# ==========================================
# 1. 配置区
# ==========================================
st.set_page_config(page_title="Deep Research 深度反思版", page_icon="🤔", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 定义 SOP (增加了反思环节)
# ==========================================

def step_1_plan(query):
    """ 策划：拆解搜索意图 """
    prompt = f"""
    目标：彻底调研 "{query}"。
    请生成 3 个互补的搜索关键词，确保覆盖不同视角。
    输出格式：JSON {{ "queries": ["词1", "词2", "词3"] }}
    """
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)['queries']

def step_2_search(queries):
    """ 执行：Tavily 搜索 """
    context = ""
    logs = []
    for q in queries:
        try:
            res = tavily.search(query=q, search_depth="advanced", max_results=3)
            logs.append(f"✅ 搜索成功：{q}")
            for item in res['results']:
                context += f"【来源：{item['url']}】\n内容：{item['content']}\n\n"
        except Exception as e:
            logs.append(f"❌ 搜索失败：{q} ({e})")
    return context, logs

def step_3_draft(query, context):
    """ 初稿：Writer 角色 """
    prompt = f"""
    你是初级研究员。基于资料写一份报告草稿。
    课题：{query}
    资料：
    {context}
    要求：逻辑通顺，覆盖资料点。
    """
    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=False
    )
    return res.choices[0].message.content

def step_4_critique(query, draft):
    """ 批评：Critic 角色 (毒舌模式) """
    prompt = f"""
    你是严厉的主编。请评审这篇草稿。
    课题：{query}
    草稿内容：
    {draft}
    
    请列出 3 个具体的修改意见（Critique），要求：
    1. 指出逻辑漏洞。
    2. 指出不够深度的地方。
    3. 指出语言啰嗦的地方。
    不要重写，只给意见。
    """
    res = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=False
    )
    return res.choices[0].message.content

def step_5_refine(query, draft, critique):
    """ 定稿：Refiner 角色 (根据意见重写) """
    prompt = f"""
    你是资深分析师。请根据【修改意见】重写这篇报告。
    
    用户课题：{query}
    原草稿：{draft}
    【修改意见】：{critique}
    
    任务：
    1. 吸纳修改意见，大幅提升文章深度。
    2. 使用Markdown格式，包含层级标题。
    3. 像专业研报一样严谨。
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
    st.header("🤔 自省式 Agent")
    st.markdown("原理：\n1. 搜索 (Tavily)\n2. 初稿 (Writer)\n3. **批判 (Critic)**\n4. **精修 (Refiner)**")

st.title("🤔 Deep Research: Self-Reflection Mode")
st.caption("Level 7: The agent that critiques itself.")

user_input = st.chat_input("请输入深度研究课题...")

if user_input:
    st.chat_message("user").write(user_input)
    
    with st.chat_message("assistant"):
        # 状态容器
        with st.status("🚀 启动深度思维链...", expanded=True) as status:
            
            # Step 1: 拆解
            status.write("🧠 1. 正在拆解问题 (Planning)...")
            qs = step_1_plan(user_input)
            status.write(f"👉 搜索方向：{qs}")
            
            # Step 2: 搜索 (最贵的步骤，只做一次)
            status.write("🌍 2. 正在并行挖掘资料 (Searching)...")
            raw_data, logs = step_2_search(qs)
            for log in logs: status.write(log)
            
            # Step 3: 初稿 (便宜的 DeepSeek 思考)
            status.write("📝 3. 正在撰写初稿 (Drafting)...")
            draft_text = step_3_draft(user_input, raw_data)
            with st.expander("查看初稿 (点击展开)"):
                st.markdown(draft_text)
            
            # Step 4: 自我批评 (核心升级点)
            status.write("🧐 4. 正在进行深度反思 (Critiquing)...")
            critique_text = step_4_critique(user_input, draft_text)
            st.info(f"**AI 的自我批评意见：**\n{critique_text}")
            
            # Step 5: 最终润色
            status.write("✍️ 5. 正在根据意见重写 (Refining)...")
            status.update(label="✅ 深度研报完成", state="complete", expanded=False)

        # 实时打印最终结果
        final_stream = step_5_refine(user_input, draft_text, critique_text)
        placeholder = st.empty()
        full_text = ""
        for chunk in final_stream:
            if chunk.choices[0].delta.content:
                full_text += chunk.choices[0].delta.content
                placeholder.markdown(full_text + "▌")
        placeholder.markdown(full_text)