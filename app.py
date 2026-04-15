import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ------------------- 页面初始化 -------------------
st.set_page_config(page_title="Stock Financial Analysis Dashboard", layout="wide")
st.title("📊 Stock Financial Analysis Dashboard")
st.markdown("ACC102 Track4 | Stable WRDS Connection | No Freeze")

# ------------------- 侧边栏输入 -------------------
st.sidebar.header("User Input Parameters")
ticker = st.sidebar.text_input("Stock Ticker", "AAPL").upper().strip()
start_year = st.sidebar.slider("Start Year", 2015, 2024, 2018)
n_years = st.sidebar.slider("Forecast Years", 1, 5, 3)
growth_rate = st.sidebar.slider("Annual Growth Rate (%)", 0.0, 20.0, 5.0)

# ------------------- 核心：WRDS连接（只连一次，缓存全局） -------------------
@st.cache_resource(show_spinner="🔌 Connecting to WRDS...", ttl=3600)
def init_wrds_connection():
    import wrds
    # 1. 读取Secrets，做严格校验
    username = st.secrets.get("wrds_username", "").strip()
    password = st.secrets.get("wrds_password", "").strip()
    
    if not username:
        st.error("❌ WRDS username not found in Streamlit Secrets!")
        st.info("💡 请在App Settings → Secrets中填写：`wrds_username = \"你的WRDS账号\"`")
        st.stop()
    if not password:
        st.error("❌ WRDS password not found in Streamlit Secrets!")
        st.info("💡 请在App Settings → Secrets中填写：`wrds_password = \"你的WRDS密码\"`")
        st.stop()

    # 2. 带超时的稳定连接，兼容不同WRDS版本
    try:
        # 优先用带密码的连接方式
        db = wrds.Connection(
            wrds_username=username,
            wrds_password=password,
            timeout=20  # 20秒超时，不会无限等待
        )
        return db
    except TypeError:
        # 兼容旧版WRDS，自动 fallback
        try:
            db = wrds.Connection(wrds_username=username)
            return db
        except Exception as e:
            st.error(f"❌ WRDS connection failed: {str(e)}")
            st.info("💡 请检查账号密码是否正确，或WRDS账号是否已激活")
            st.stop()
    except Exception as e:
        st.error(f"❌ WRDS connection failed: {str(e)}")
        st.info("💡 请检查网络、账号权限，或联系WRDS支持")
        st.stop()

# ------------------- 数据加载（缓存1小时，不重复查询） -------------------
@st.cache_data(show_spinner="📥 Loading financial data...", ttl=3600)
def load_financial_data(ticker, start_year):
    db = init_wrds_connection()
    # 安全处理股票代码
    safe_ticker = ticker.upper().strip()
    
    # WRDS Compustat标准查询语句
    query = """
    SELECT fyear, revt, ni, roe, at, lt, prcc_f, csho
    FROM comp.funda
    WHERE UPPER(tic) = %(ticker)s
      AND fyear >= %(start_year)s
      AND indfmt = 'INDL'
      AND datafmt = 'STD'
      AND popsrc = 'D'
      AND consol = 'C'
    ORDER BY fyear
    """
    
    try:
        df = db.raw_sql(query, params={"ticker": safe_ticker, "start_year": int(start_year)})
        if df.empty:
            return None, "No data found"
        
        # 重命名列，方便后续计算
        df = df.rename(columns={
            "fyear": "Year",
            "revt": "Revenue",
            "ni": "Net_Income",
            "roe": "ROE",
            "at": "Total_Assets",
            "lt": "Total_Liabilities",
            "prcc_f": "Stock_Price",
            "csho": "Shares_Outstanding"
        })
        return df.round(2), "Success"
    except Exception as e:
        return None, f"Query error: {str(e)}"

# ------------------- 数据处理与指标计算 -------------------
def process_data(df):
    # 清洗数据，去除空值和异常值
    df = df.dropna().copy()
    df = df[(df["Revenue"] > 0) & (df["Total_Assets"] > 0) & (df["Shares_Outstanding"] > 0)]
    
    if df.empty:
        return None
    
    # 计算核心财务指标
    df["Profit_Margin(%)"] = (df["Net_Income"] / df["Revenue"] * 100).round(2)
    df["Debt_Ratio(%)"] = (df["Total_Liabilities"] / df["Total_Assets"] * 100).round(2)
    df["EPS"] = (df["Net_Income"] / df["Shares_Outstanding"]).round(2)
    return df

# ------------------- 预测功能 -------------------
def create_forecast(df, n_years, growth_rate):
    last_year = int(df["Year"].max())
    last_rev = df["Revenue"].iloc[-1]
    last_prof = df["Net_Income"].iloc[-1]
    
    forecast = pd.DataFrame({
        "Year": [last_year + i for i in range(1, n_years + 1)],
        "Forecast_Revenue": [last_rev * (1 + growth_rate / 100) ** i for i in range(1, n_years + 1)],
        "Forecast_Net_Income": [last_prof * (1 + growth_rate / 100) ** i for i in range(1, n_years + 1)]
    }).round(2)
    return forecast

# ------------------- 主逻辑执行 -------------------
# 1. 加载数据
raw_df, status = load_financial_data(ticker, start_year)

if raw_df is None:
    st.error(f"❌ Failed to load data: {status}")
    st.info("💡 Try a valid ticker like AAPL, MSFT, TSLA, or check your WRDS account")
    st.stop()

# 2. 处理数据
df = process_data(raw_df)
if df is None or df.empty:
    st.error("❌ No valid financial data after processing")
    st.stop()

# 3. 生成预测
forecast = create_forecast(df, n_years, growth_rate)

# ------------------- 页面展示 -------------------
st.success(f"✅ Real WRDS Compustat data loaded successfully for {ticker}")

# 1. 财务数据表
st.subheader("📋 Historical Financial Data")
st.dataframe(df, use_container_width=True)

# 2. 趋势图表
st.subheader("📈 Trend Analysis")
col1, col2 = st.columns(2)

with col1:
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(df["Year"], df["Stock_Price"], marker="o", color="#1f77b4", linewidth=2)
    ax1.set_title("Stock Price Trend", fontsize=12)
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Stock Price (USD)")
    ax1.grid(alpha=0.3)
    st.pyplot(fig1)

with col2:
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.bar(df["Year"] - 0.2, df["Revenue"], width=0.4, label="Revenue", color="#ff7f0e", alpha=0.8)
    ax2.bar(df["Year"] + 0.2, df["Net_Income"], width=0.4, label="Net Income", color="#2ca02c", alpha=0.8)
    ax2.legend()
    ax2.set_title("Revenue vs Net Income", fontsize=12)
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Amount (USD Millions)")
    ax2.grid(alpha=0.3)
    st.pyplot(fig2)

# 3. 核心KPI
st.subheader("🎯 Key Financial Metrics")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Average ROE", f"{df['ROE'].mean():.1f}%")
k2.metric("Average Profit Margin", f"{df['Profit_Margin(%)'].mean():.1f}%")
k3.metric("Average Debt Ratio", f"{df['Debt_Ratio(%)'].mean():.1f}%")
k4.metric("Average EPS", f"{df['EPS'].mean():.2f}")

# 4. 预测数据
st.subheader("🔮 Financial Forecast")
st.dataframe(forecast, use_container_width=True)

# 5. 预测图表
fig3, ax3 = plt.subplots(figsize=(10, 5))
ax3.plot(df["Year"], df["Revenue"], marker="o", label="Historical Revenue", color="#ff7f0e", linewidth=2)
ax3.plot(forecast["Year"], forecast["Forecast_Revenue"], marker="o", linestyle="--", label="Forecast Revenue", color="#ffbb78", linewidth=2)
ax3.plot(df["Year"], df["Net_Income"], marker="o", label="Historical Net Income", color="#2ca02c", linewidth=2)
ax3.plot(forecast["Year"], forecast["Forecast_Net_Income"], marker="o", linestyle="--", label="Forecast Net Income", color="#98df8a", linewidth=2)
ax3.set_title("Historical and Forecast Financial Trend", fontsize=14)
ax3.set_xlabel("Year")
ax3.set_ylabel("Amount (USD Millions)")
ax3.legend()
ax3.grid(alpha=0.3)
st.pyplot(fig3)

# 6. 下载功能
st.subheader("📥 Download Data")
col_d1, col_d2 = st.columns(2)
col_d1.download_button(
    label="Download Historical Data CSV",
    data=df.to_csv(index=False, encoding="utf-8-sig"),
    file_name=f"{ticker}_financial_data.csv",
    mime="text/csv"
)
col_d2.download_button(
    label="Download Forecast Data CSV",
    data=forecast.to_csv(index=False, encoding="utf-8-sig"),
    file_name=f"{ticker}_forecast.csv",
    mime="text/csv"
)

# 7. 免责声明
st.info("""
This dashboard is for educational purposes only. It is not professional investment advice.
Data source: WRDS Compustat
""")
