import streamlit as st
from openai import OpenAI
from tavily import TavilyClient
import pandas as pd
import json
import concurrent.futures
import datetime
from docx import Document
from io import BytesIO
from pypdf import PdfReader
import matplotlib.pyplot as plt

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(page_title="DeepSeek 数据分析师 (Level 13)", page_icon="📈", layout="wide")

deepseek_key = st.secrets.get("DEEPSEEK_API_KEY")
tavily_key = st.secrets.get("TAVILY_API_KEY")

if not deepseek_key or not tavily_key:
    st.error("❌ 请检查 Secrets 配置！")
    st.stop()

client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
tavily = TavilyClient(api_key=tavily_key)

# ==========================================
# 2. 工具函数：读取文件 (支持 PDF 和 Excel)
# ==========================================
def read_file(uploaded_file):
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    if file_type == 'pdf':
        try:
            pdf = PdfReader(uploaded_file)
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            return "text", text[:20000]
        except:
            return "error", "PDF 读取失败"
            
    elif file_type in ['xlsx', 'csv']:
        try:
            if file_type == 'csv':
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            return "dataframe", df
        except:
            return "error", "表格读取失败"
    
    return "error", "不支持的文件格式"

# ==========================================
# 3. 核心大脑：数据分析引擎 (Code Interpreter)
# ==========================================

def analyze_data_with_code(query, df):
    """ 
    让 DeepSeek 写 Python 代码来分析 DataFrame 
    """
    # 告诉 AI 数据的结构
    df_info = df.head(3).to_markdown()
    columns = list(df.columns)
    
    prompt = f"""
    你是一个 Python 数据分析专家。用户上传了一个 Pandas DataFrame (变量名为 `df`)。
    
    【数据预览】：
    {df_info}
    
    【列名】：{columns}
    
    【用户需求】："{query}"
    
    请编写一段 Python 代码来满足用户的分析需求。
    
    要求：
    1. 代码必须是可以执行的 Python 代码。
    2. 如果需要画图，请使用 `matplotlib.pyplot` (别名 plt)。
    3. **关键**：将最终的分析结论或图表对象赋值给一个叫 `result` 的变量。
       - 如果是画图，`result = plt.gcf()`
       - 如果是计算数字，`result = "计算结果是..."`
       - 如果是筛选数据，`result = df_filtered`
    4. 不要包含 ```python 标记，直接输出代码内容。
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0 # 代码必须严谨
    )
    return response.choices[0].message.content.replace("```python", "").replace("```", "").strip()

# ==========================================
# 4. 页面 UI
# ==========================================
with st.sidebar:
    st.header("📈 Level 13: Data Analyst")
    uploaded_file = st.file_uploader("📂 上传资料 (PDF / Excel / CSV)", type=["pdf", "xlsx", "csv"])
    
    data_context = None
    data_type = None
    
    if uploaded_file:
        data_type, data_context = read_file(uploaded_file)
        if data_type == "dataframe":
            st.success("✅ 表格加载成功！")
            st.dataframe(data_context.head(5)) # 预览前5行
        elif data_type == "text":
            st.success(f"✅ 文档加载成功 ({len(data_context)} 字)")

st.title("📈 DeepSeek 智能数据分析师")
st.caption("Level 13: Talk to your Excel/CSV Data")

user_input = st.chat_input("请输入指令 (例如：画出销售额随时间的变化趋势)...")

if user_input:
    st.chat_message("user").write(user_input)
    
    with st.chat_message("assistant"):
        # 场景 A: 纯数据分析 (如果上传了表格)
        if data_type == "dataframe":
            df = data_context # 拿到数据
            
            with st.status("💻 正在编写分析代码...", expanded=True) as status:
                # 1. 让 AI 写代码
                code = analyze_data_with_code(user_input, df)
                st.code(code, language='python') # 展示 AI 写的代码
                
                # 2. 执行代码 (高危操作，但在本地很爽)
                status.write("⚙️ 正在执行代码...")
                try:
                    local_vars = {"df": df, "plt": plt, "pd": pd}
                    exec(code, {}, local_vars) # 执行！
                    result = local_vars.get('result', '没有检测到 result 变量')
                    
                    status.update(label="✅ 分析完成", state="complete")
                    
                    # 3. 展示结果
                    st.divider()
                    st.write("### 📊 分析结果")
                    
                    # 如果结果是图表
                    if hasattr(result, 'canvas'): 
                        st.pyplot(result)
                    # 如果结果是表格
                    elif isinstance(result, pd.DataFrame):
                        st.dataframe(result)
                    # 其他文本结果
                    else:
                        st.write(result)
                        
                except Exception as e:
                    status.update(label="❌ 代码执行出错", state="error")
                    st.error(f"报错详情: {e}")
                    
        # 场景 B: 之前的混合搜索 (如果没有表格，或者只是PDF)
        else:
            st.info("💡 这是一个普通搜索/文档问答模式 (未检测到表格)")
            # 这里保留之前的逻辑，简写一下，方便演示 Level 13 核心
            # ... (你可以把 Level 11 的逻辑贴回来，或者专注于测试数据功能)
            st.write("请上传 Excel 文件以体验 Level 13 的核心功能！")