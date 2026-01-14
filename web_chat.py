import streamlit as st
from openai import OpenAI
from duckduckgo_search import DDGS  # 👈 新武器：联网搜索工具
import time

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 全网情报局", page_icon="🌍", layout="wide")

api_key = st.secrets.get("DEEPSEEK_API_KEY")
if not api_key:
    st.error("❌ 请配置 API Key")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ==========================================
# 2. 侧边栏
# ==========================================
with st.sidebar:
    st.header("🌍 情报控制台")
    st.markdown("这里是你的私人 AI 情报员。输入关键词，我来帮你跑腿。")
    
    # 搜索条数控制
    max_results = st.slider("搜索文章数量", 5, 20, 10)
    
    if st.button("🗑️ 清空情报"):
        st.session_state.messages = []
        if "report" in st.session_state:
            del st.session_state["report"]
        st.rerun()

# ==========================================
# 3. 核心功能：联网搜索函数
# ==========================================
def search_web(query, num_results=10):
    """ 使用 DuckDuckGo 搜索网络信息 """
    results = []
    with DDGS() as ddgs:
        # keywords: 关键词, max_results: 数量
        search_gen = ddgs.text(query, max_results=num_results)
        for r in search_gen:
            results.append(r)
    return results

# ==========================================
# 4. 主界面逻辑
# ==========================================
st.title("🌍 DeepSeek AI 全网情报局")
st.caption("Level 5: AI Search Agent (Real-time Web Access)")

# 输入框
user_query = st.chat_input("请输入你想调研的主题（例如：DeepSeek最新动态 / 2024 AI 发展趋势）...")

if user_query:
    # A. 显示用户的指令
    st.chat_message("user").write(user_query)
    
    # B. Agent 开始行动
    with st.chat_message("assistant"):
        status_box = st.status("🕵️‍♂️ 情报员出动中...", expanded=True)
        
        # --- 第一步：联网搜索 ---
        status_box.write(f"🔍 正在全网搜索：{user_query} ...")
        try:
            # 执行搜索
            search_data = search_web(user_query, max_results)
            
            if not search_data:
                status_box.update(label="❌ 搜索无结果", state="error")
                st.stop()
                
            status_box.write(f"✅ 已抓取 {len(search_data)} 条相关情报，正在阅读...")
            
            # 将搜索结果拼接成文本，喂给 AI
            context_text = ""
            for idx, item in enumerate(search_data):
                context_text += f"【来源 {idx+1}】标题：{item['title']}\n链接：{item['href']}\n摘要：{item['body']}\n\n"
                
        except Exception as e:
            status_box.update(label="❌ 网络连接失败", state="error")
            st.error(f"搜索报错: {e}")
            st.stop()

        # --- 第二步：AI 思考与总结 ---
        status_box.write("🧠 正在整理情报并撰写报告...")
        
        system_prompt = f"""
        你是一个专业的情报分析师。你的任务是根据提供的互联网搜索结果，写一份深度的【情报简报】。
        
        要求：
        1. 必须基于提供的【搜索结果】回答，不要瞎编。
        2. 格式要求：
           - 🏆 **核心结论**：一句话总结最重要的信息。
           - 📝 **详细动态**：分点叙述，逻辑清晰。
           - 🔗 **参考来源**：在文末列出关键链接。
        3. 语言风格：专业、客观、精炼。
        """
        
        user_prompt = f"""
        用户调研主题：{user_query}
        
        搜索到的互联网情报：
        {context_text}
        
        请开始撰写报告：
        """
        
        # 调用 DeepSeek
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=True  # 开启流式输出，看着更爽
        )
        
        # --- 第三步：流式输出报告 ---
        status_box.update(label="✅ 报告生成完毕", state="complete", expanded=False)
        
        # 实时打印文字
        report_placeholder = st.empty()
        full_report = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_report += content
                report_placeholder.markdown(full_report + "▌")
        
        report_placeholder.markdown(full_report)