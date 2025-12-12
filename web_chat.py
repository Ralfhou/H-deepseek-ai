import streamlit as st
from openai import OpenAI
import PyPDF2
from docx import Document
import pandas as pd  # 👈 新增：这是专门处理 Excel/数据的库

# 1. 页面配置
st.set_page_config(page_title="DeepSeek 知识库 Pro", page_icon="🧠", layout="wide")

# 初始化 session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 2. 定义万能读取函数 (支持 PDF/Word/Txt/Excel)
# ==========================================
def read_files(uploaded_files):
    all_content = ""
    file_summary = []  # 用来记录读了哪些文件
    
    for file in uploaded_files:
        try:
            content = ""
            # A. 处理 PDF
            if file.name.endswith(".pdf"):
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    content += page.extract_text() + "\n"
            
            # B. 处理 Word
            elif file.name.endswith(".docx"):
                doc = Document(file)
                for para in doc.paragraphs:
                    content += para.text + "\n"
            
            # C. 处理 TXT
            elif file.name.endswith(".txt"):
                content = file.read().decode("utf-8")
            
            # D. 处理 Excel (新功能!)
            elif file.name.endswith(".xlsx") or file.name.endswith(".xls"):
                # 读取 Excel 为表格数据
                df = pd.read_excel(file)
                # 把表格转成文字描述，喂给 AI
                content = df.to_markdown(index=False)
                # 在网页侧边栏显示一下表格预览，看起来很酷
                with st.sidebar.expander(f"📊 {file.name} 预览"):
                    st.dataframe(df)

            # 把单个文件内容打包
            if content:
                all_content += f"\n--- 文件名：{file.name} ---\n{content}\n"
                file_summary.append(file.name)
                
        except Exception as e:
            st.sidebar.error(f"❌ 读取 {file.name} 失败: {str(e)}")
            
    return all_content, file_summary

# ==========================================
# 3. 侧边栏：控制台
# ==========================================
with st.sidebar:
    st.title("🎛️ 知识库控制台")
    
    # 创造力滑块
    temperature = st.slider("🧠 思考发散度", 0.0, 1.3, 0.7, 0.1)
    
    st.divider()
    
    # 📂 多文件上传区 (注意：accept_multiple_files=True)
    st.subheader("📂 投喂文档 (支持多选)")
    uploaded_files = st.file_uploader(
        "按住 Ctrl 可多选文件 (PDF/Word/Excel/Txt)", 
        type=["pdf", "docx", "txt", "xlsx", "xls"],
        accept_multiple_files=True 
    )
    
    # 处理文件逻辑
    files_text = ""
    if uploaded_files:
        files_text, file_names = read_files(uploaded_files)
        if files_text:
            st.success(f"✅ 已加载 {len(uploaded_files)} 个文件")
            st.caption(f"包含: {', '.join(file_names)}")
    
    st.divider()
    
    # 清空和下载
    if st.button("🗑️ 清空所有对话"):
        st.session_state.messages = []
        if "last_files" in st.session_state:
            del st.session_state["last_files"]
        st.rerun()

    chat_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    st.download_button("📥 导出对话记录", chat_str, "chat_history.txt")

# ==========================================
# 4. API 客户端 (从保险箱取 Key)
# ==========================================
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"], 
    base_url="https://api.deepseek.com"
)

# ==========================================
# 5. 主界面
# ==========================================
st.title("Hou DeepSeek 知识库 Pro")

# 智能系统提示词注入
# 只有当文件列表发生变化，或者第一次上传时，才向 AI 发送文件内容
current_file_names = [f.name for f in uploaded_files] if uploaded_files else []
previous_file_names = st.session_state.get("last_files", [])

if uploaded_files and current_file_names != previous_file_names:
    # 记录这次的文件名，防止刷新时重复发送
    st.session_state.last_files = current_file_names
    
    # 构造超级提示词
    system_msg = {
        "role": "system", 
        "content": f"""你是一个智能知识库助手。用户上传了以下文件内容：
{files_text}

请根据以上文件内容，准确回答用户的问题。如果问题超出文件范围，请利用你的通用知识回答。"""
    }
    
    # 插入到对话开头
    st.session_state.messages.insert(0, system_msg)
    # 它是 AI，给个面子让它打个招呼
    st.session_state.messages.append({
        "role": "assistant", 
        "content": f"📚 我已阅读完以下文件：\n- " + "\n- ".join(current_file_names) + "\n\n请问我想了解什么？（比如让我是分析数据，或者对比文档）"
    })

# 移除文件后的清理
if not uploaded_files and "last_files" in st.session_state:
    del st.session_state["last_files"]

# 渲染历史消息
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 处理输入
if user_input := st.chat_input("输入问题..."):
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=st.session_state.messages,
            stream=True,
            temperature=temperature
        )
        response = st.write_stream(stream)
    
    st.session_state.messages.append({"role": "assistant", "content": response})