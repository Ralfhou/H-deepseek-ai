import streamlit as st
from openai import OpenAI
from tavily import TavilyClient # 👈 换成专业搜索客户端
import time

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 全网情报局 (Pro)", page_icon="📡", layout="wide")

# 获取 DeepSeek Key
deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
# 获取 Tavily Key (搜索专用)
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 缺少 API Key，请在 Secrets 中配置 DEEPSEEK_API_KEY 和 TAVILY_API_KEY")
    st.stop()

# 初始化客户端
client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily_client = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 侧边栏
# ==========================================
with st.sidebar:
    st.header("📡 Pro 版情报控制台")
    st.caption("Powered by Tavily (Enterprise Search)")
    
    # 搜索深度选择
    search_depth = st.radio("搜索模式", ["basic (快速)", "advanced (深度)"], index=0)
    depth_val = "basic" if "basic" in search_depth else "advanced"
    
    if st.button("🗑️ 清空情报"):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 3. 主界面逻辑
# ==========================================
st.title("📡 DeepSeek 全网情报局 (Pro)")
st.caption("Level 5: Enterprise Search Agent")

user_query = st.chat_input("请输入调研主题（例如：DeepSeek vs OpenAI 评测）...")

if user_query:
    st.chat_message("user").write(user_query)
    
    with st.chat_message("assistant"):
        status_box = st.status("🕵️‍♂️ 特工出动中...", expanded=True)
        
        # --- A. 联网搜索 (Tavily) ---
        status_box.write(f"🔍 正在连接 Tavily 搜索网络：{user_query} ...")
        try:
            # Tavily 会自动把网页内容清洗成干净的文本
            response = tavily_client.search(
                query=user_query, 
                search_depth=depth_val,
                max_results=5 # 5篇精华通常足够
            )
            
            search_results = response.get("results", [])
            
            if not search_results:
                status_box.update(label="❌ 未找到相关信息", state="error")
                st.stop()
                
            status_box.write(f"✅ 已获取 {len(search_results)} 份高价值情报，正在分析...")
            
            # 拼接上下文
            context_text = ""
            for item in search_results:
                context_text += f"【来源】{item['title']}\n链接：{item['url']}\n内容摘要：{item['content']}\n\n"
                
        except Exception as e:
            status_box.update(label="❌ 搜索接口报错", state="error")
            st.error(f"Tavily Error: {e}")
            st.stop()

        # --- B. AI 深度分析 ---
        status_box.write("🧠 DeepSeek 正在撰写深度研报...")
        
        system_prompt = f"""
        你是一名首席情报分析师。请基于以下搜索结果撰写报告。
        
        搜索数据：
        {context_text}
        
        要求：
        1. 必须引用上述数据，严禁编造。
        2. 使用 Markdown 格式。
        3. 包含：【核心结论】、【详细动态分析】、【相关链接】。
        """
        
        # 流式输出
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"分析主题：{user_query}"}
            ],
            stream=True
        )
        
        status_box.update(label="✅ 研报生成完毕", state="complete", expanded=False)
        
        # 实时打印
        report_placeholder = st.empty()
        full_text = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_text += chunk.choices[0].delta.content
                report_placeholder.markdown(full_text + "▌")
        report_placeholder.markdown(full_text)