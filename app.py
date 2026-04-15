import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ------------------- Page Setup -------------------
st.set_page_config(page_title="Stock Financial Analysis Dashboard", layout="wide")
plt.rcParams['axes.unicode_minus'] = False

# 全局缓存开关（关键：防止重复连接WRDS导致卡住）
st.session_state.setdefault("wrds_connected", False)
st.session_state.setdefault("df_cache", None)

# ------------------- 标题 -------------------
st.title("📊 Stock Financial Analysis Dashboard")
st.markdown("""
This interactive dashboard uses **real WRDS Compustat data** for financial analysis.  
**ACC102 Track4 | Stable WRDS Connection | No Freeze**
""")

# ------------------- Sidebar -------------------
st.sidebar.header("User Input Parameters")
ticker = st.sidebar.text_input("Stock Ticker", "AAPL").upper().strip()
start_year = st.sidebar.slider("Start Year", 2015, 2024, 2018)
n_years = st.sidebar.slider("Forecast Years", 1, 5, 3)
growth_rate = st.sidebar.slider("Annual Growth Rate (%)", 0.0, 20.0, 5.0)

# ------------------- 稳定 WRDS 连接（只连一次，不重复卡死） -------------------
@st.cache_resource(show_spinner="🔌 Connecting WRDS...")
def stable_wrds_connection():
    try:
        import wrds
    except ImportError:
        st.error("❌ wrds package missing → add `wrds` to requirements.txt")
        st.stop()

    username = st.secrets.get("wrds_username", "")
    password = st.secrets.get("wrds_password", "")

    if not username or not password:
        st.error("❌ WRDS username/password not set in Streamlit secrets")
        st.stop()

    try:
        # 稳定连接，带超时
        db = wrds.Connection(
            wrds_username=username,
            wrds_password=password,
            timeout=25
        )
        return db
    except Exception as e:
        st.error(f"❌ WRDS connect failed: {str(e)}")
        st.stop()

# ------------------- 数据加载（缓存，不重复查询） -------------------
@st.cache_data(show_spinner="📥 Loading data...", ttl=3600)
def get_data(ticker, start_year):
    db = stable_wrds_connection()
    ticker_safe = ticker.upper()

    query = """
    SELECT fyear, revt, ni, roe, at, lt, prcc_f, csho
    FROM comp.funda
    WHERE UPPER(tic) = %(ticker)s
      AND fyear >= %(start_year)s
      AND indfmt = 'INDL' AND datafmt = 'STD'
      AND popsrc = 'D' AND consol = 'C'
    ORDER BY fyear
    """

    try:
        df = db.raw_sql(query, params={"ticker": ticker_safe, "start_year": start_year})
        if df.empty:
            return None

        df = df.rename(columns={
            "fyear": "Year", "revt": "Revenue", "ni": "Net_Income",
            "roe": "ROE", "at": "Total_Assets", "lt": "Total_Liabilities",
            "prcc_f": "Stock_Price", "csho": "Shares_Outstanding"
        })
        return df
    except:
        return None

# ------------------- 数据处理 -------------------
def calc_metrics(df):
    df = df.dropna().copy()
    df["Profit_Margin(%)"] = (df.Net_Income / df.Revenue * 100).round(2)
    df["Debt_Ratio(%)"] = (df.Total_Liabilities / df.Total_Assets * 100).round(2)
    df["EPS"] = (df.Net_Income / df.Shares_Outstanding).round(2)
    return df

def make_forecast(df, n, rate):
    last = df.iloc[-1]
    years = [last.Year + i for i in range(1, n+1)]
    rev = [last.Revenue * (1+rate/100)**i for i in range(1, n+1)]
    income = [last.Net_Income * (1+rate/100)**i for i in range(1, n+1)]
    return pd.DataFrame({"Year": years, "Forecast_Revenue": rev, "Forecast_Net_Income": income}).round(2)

# ------------------- 主逻辑 -------------------
df = get_data(ticker, start_year)

if df is None or df.empty:
    st.error(f"❌ No data for {ticker} from {start_year}")
    st.info("💡 Try: AAPL, MSFT, AMZN, GOOG, TSLA")
    st.stop()

df = calc_metrics(df)
st.success(f"✅ Real WRDS data loaded: {ticker}")

# ------------------- 展示 -------------------
st.subheader("📋 Financial Data")
st.dataframe(df, use_container_width=True)

st.subheader("📈 Trend Charts")
c1, c2 = st.columns(2)

with c1:
    fig1, ax1 = plt.subplots()
    ax1.plot(df.Year, df.Stock_Price, marker="o", color="#1f77b4")
    ax1.set_title("Stock Price")
    st.pyplot(fig1)

with c2:
    fig2, ax2 = plt.subplots()
    ax2.bar(df.Year-0.2, df.Revenue, 0.4, label="Revenue")
    ax2.bar(df.Year+0.2, df.Net_Income, 0.4, label="Net Income")
    ax2.legend()
    ax2.set_title("Revenue vs Income")
    st.pyplot(fig2)

# ------------------- KPIs -------------------
st.subheader("🎯 Key Metrics")
k1,k2,k3,k4 = st.columns(4)
k1.metric("Avg ROE", f"{df.ROE.mean():.1f}%")
k2.metric("Profit Margin", f"{df['Profit_Margin(%)'].mean():.1f}%")
k3.metric("Debt Ratio", f"{df['Debt_Ratio(%)'].mean():.1f}%")
k4.metric("Avg EPS", f"{df.EPS.mean():.2f}")

# ------------------- 预测 -------------------
st.subheader("🔮 Forecast")
fore = make_forecast(df, n_years, growth_rate)
st.dataframe(fore, use_container_width=True)

# ------------------- 下载 -------------------
st.subheader("📥 Download")
col1, col2 = st.columns(2)
col1.download_button("Data CSV", df.to_csv(index=False), f"{ticker}_data.csv")
col2.download_button("Forecast CSV", fore.to_csv(index=False), f"{ticker}_forecast.csv")

# ------------------- 提交用备注 -------------------
st.caption("✅ ACC102 Track4 | Real WRDS Compustat | Stable Connection | No Freeze")
