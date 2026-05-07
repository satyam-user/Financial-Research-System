import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
from fpdf import FPDF
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from lightweight_charts_v5 import lightweight_charts_v5_component 
from streamlit_lightweight_charts import renderLightweightCharts

# --- THE GRAND UNIFICATION IMPORTS ---
try:
    from dcf_nlp import run_sentiment_analysis
    HAS_NLP = True
except Exception as e:
    HAS_NLP = False
    NLP_ERROR = e

try:
    from dcf_consensus import get_dupont_and_health_metrics
    HAS_CONSENSUS = True
except Exception as e:
    HAS_CONSENSUS = False
    CONSENSUS_ERROR = e

try:
    from dcf_altdata import run_altdata_valuation
    HAS_ALTDATA = True
except Exception as e:
    HAS_ALTDATA = False
    ALTDATA_ERROR = e

st.set_page_config(page_title="Financial Research System", page_icon="💹", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f17; color: #e2e8f0; }
    .conclusion-box { background-color: #161b22; border-left: 4px solid #3b82f6; padding: 20px; margin-top: -15px; margin-bottom: 50px; border-radius: 0 0 8px 8px; font-size: 0.95rem; color: #94a3b8; line-height: 1.6; }
    .module-box { background-color: #1e293b; border: 1px solid #334155; border-left: 4px solid #8b5cf6; padding: 20px; border-radius: 8px; margin-bottom: 30px; font-size: 0.95rem; line-height: 1.5; }
    h2 { color: #60a5fa; margin-top: 40px; text-transform: uppercase; font-size: 1.3rem; border-bottom: 1px solid #1e293b; padding-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

def clean_for_pdf(text):
    """
    Cleans HTML tags and special characters so the PDF report 
    looks professional and doesn't show code.
    """
    replacements = {
        "<b>": "", 
        "</b>": "", 
        "<br>": "\n", 
        "🟢": "", 
        "🔴": "", 
        "⚪": "", 
        "•": "-", 
        "[-]": "-", 
        "**": ""
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def resolve_ticker(user_input):
    user_input = user_input.strip()
    if '.' in user_input: return user_input.upper()
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={user_input}"
        headers = {'User-Agent': 'Mozilla/5.0'} 
        response = requests.get(url, headers=headers).json()
        quotes = response.get('quotes', [])
        for quote in quotes:
            if quote.get('exchange') in ['NSI', 'BSE']: return quote['symbol']
        for quote in quotes:
            if quote.get('quoteType') == 'EQUITY': return quote['symbol']
        return user_input.upper()
    except: return user_input.upper()

# ==========================================
# ANTI-BAN CACHING FUNCTIONS (Definitions only)
# ==========================================
@st.cache_resource
def get_yf_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

@st.cache_data(ttl=3600) 
def fetch_fundamentals(ticker_symbol):
    session = get_yf_session()
    stock = yf.Ticker(ticker_symbol, session=session)
    return stock.info

@st.cache_data(ttl=3600)
def pull_all_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.financials.T, stock.balance_sheet.T, stock.cashflow.T, stock.info

def format_kmb(num):
    if pd.isna(num) or num == 0: return "0"
    is_neg = num < 0
    num = abs(num)
    if num >= 1e9: val = f"{num/1e9:.2f}B"
    elif num >= 1e6: val = f"{num/1e6:.2f}M"
    elif num >= 1e3: val = f"{num/1e3:.2f}K"
    else: val = f"{num:.2f}"
    return f"-{val}" if is_neg else val

st.title("💹 Financial Research System")
st.markdown("Deep dive into fundamentals and technicals of companies.")

query = st.text_input("Enter any company name (e.g., Microsoft, Infosys , Apple):", "")

if query:
    ticker = resolve_ticker(query)
    
    # ==========================================
    # PART 1: FUNDAMENTAL ANALYSIS SECTION
    # ==========================================
    with st.spinner(f"Compiling institutional ledgers and running analysis for {ticker}..."):
        try:
            inc, bs, cf, info = pull_all_data(ticker)
            name = info.get('shortName', ticker)
            
            sector, industry = str(info.get('sector', '')), str(info.get('industry', ''))
            is_bank = 'Financial' in sector or 'Bank' in industry or 'Credit' in industry
            
            currency_code = info.get('currency', info.get('financialCurrency', 'USD'))
            if currency_code == 'INR': sym, pdf_sym = '₹', 'Rs. ' 
            elif currency_code == 'EUR': sym, pdf_sym = '€', 'EUR '
            elif currency_code == 'GBP': sym, pdf_sym = '£', 'GBP '
            else: sym, pdf_sym = '$', '$'
            fin_sym = '$' 
            
            price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            
            if HAS_ALTDATA: intrinsic_val = run_altdata_valuation(ticker)
            else: intrinsic_val = info.get('targetMeanPrice', price * 1.08)

            beta_val = info.get('beta', 1.0)
            de_ratio_raw = info.get('debtToEquity', 0)
            de_val = 0.0 if pd.isna(de_ratio_raw) else float(de_ratio_raw)
            
            st.divider()
            
            # --- SAFE MARGIN CALCULATION FOR TOP BAR ---
            try:
                temp_stock = yf.Ticker(ticker)
                top_ni = temp_stock.financials.loc['Net Income'].iloc[0]
                top_rev = temp_stock.financials.loc['Total Revenue'].iloc[0]
                top_margin = (top_ni / top_rev) * 100 if top_rev != 0 else 0
            except:
                top_margin = info.get('profitMargins', 0) * 100

            # --- METRIC DISPLAY ---
            k1, k2, k3, k4, k5, k6 = st.columns(6)

            k1.metric("Market Price", f"{sym}{price:,.2f}")
            k2.metric("Intrinsic Target", f"{sym}{intrinsic_val:,.2f}")
            k3.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")
            k4.metric("Profit Margin", f"{top_margin:.1f}%")

            if is_bank: 
                k5.metric("Debt-to-Equity", "N/A (Bank)")
            elif de_val <= 0.01: 
                k5.metric("Debt-to-Equity", "Debt Free")
            else: 
                k5.metric("Debt-to-Equity", f"{de_val:.2f}")

            k6.metric("Beta (Risk)", f"{beta_val:.2f}")

            st.divider()
            
            # --- THE AI & NLP DASHBOARD SECTION ---
            st.header("Advanced AI & NLP updates")
            nlp_text, consensus_text = "NLP Offline", "Consensus Offline"
            
            ai1, ai2 = st.columns(2)
            with ai1:
                st.markdown("### 📰 Sentiment & NLP Engine")
                if HAS_NLP:
                    nlp_text = str(run_sentiment_analysis(ticker))
                    st.markdown(f"<div class='module-box'>{nlp_text}</div>", unsafe_allow_html=True)
                else: st.warning(f"Error loading dcf_nlp.py: {NLP_ERROR}")
                    
            with ai2:
                st.markdown("### 🕵️‍♂️ Financial Health")
                if HAS_CONSENSUS:
                    consensus_text = str(get_dupont_and_health_metrics(ticker))
                    st.markdown(f"<div class='module-box'>{consensus_text}</div>", unsafe_allow_html=True)
                else: st.warning(f"Error loading dcf_consensus.py: {CONSENSUS_ERROR}")

            st.divider()

            slice_idx = min(4, len(inc))
            try: years = [str(date.year) for date in inc.index[:slice_idx]][::-1]
            except: years = [f"Year {i}" for i in range(1, slice_idx+1)]

            rev = inc.get('Total Revenue', inc.get('Operating Revenue', inc.iloc[:, 0])).iloc[:slice_idx][::-1].fillna(0)
            ni = inc.get('Net Income', rev * 0.1).iloc[:slice_idx][::-1].fillna(0)
            gp = inc.get('Gross Profit', rev * 0.4).iloc[:slice_idx][::-1].fillna(0)
            op_inc = inc.get('Operating Income', rev * 0.2).iloc[:slice_idx][::-1].fillna(0)
            ebitda = inc.get('EBITDA', op_inc * 1.2).iloc[:slice_idx][::-1].fillna(0)
            interest = inc.get('Interest Expense', pd.Series([-1]*len(inc))).iloc[:slice_idx][::-1].fillna(-1).abs().replace(0, 1)
            
            debt = bs.get('Total Debt', pd.Series([0]*len(bs))).iloc[:slice_idx][::-1].fillna(0)
            equity = bs.get('Stockholders Equity', pd.Series([1]*len(bs))).iloc[:slice_idx][::-1].fillna(1)
            assets = bs.get('Total Assets', pd.Series([1]*len(bs))).iloc[:slice_idx][::-1].fillna(1)
            liab = bs.get('Total Liabilities Net Minority Interest', bs.get('Total Liabilities', pd.Series([1]*len(bs)))).iloc[:slice_idx][::-1].fillna(1)

            ca_row, cl_row = bs.get('Current Assets'), bs.get('Current Liabilities')
            if ca_row is None: ca_row = bs.get('Total Current Assets')
            if cl_row is None: cl_row = bs.get('Total Current Liabilities')
            has_wc_data = ca_row is not None and cl_row is not None and not ca_row.isna().all()
            
            if has_wc_data:
                curr_assets = ca_row.iloc[:slice_idx][::-1].fillna(0)
                curr_liab = cl_row.iloc[:slice_idx][::-1].fillna(0)
            else:
                curr_assets, curr_liab = pd.Series([0]*slice_idx, index=years), pd.Series([0]*slice_idx, index=years)

            ocf = cf.get('Operating Cash Flow', ni * 1.1).iloc[:slice_idx][::-1].fillna(0)
            capex = cf.get('Capital Expenditure', rev * -0.05).iloc[:slice_idx][::-1].fillna(0).abs()
            fcf = cf.get('Free Cash Flow', ocf - capex).iloc[:slice_idx][::-1].fillna(0)

            c1, c2 = st.columns(2)
            with c1:
                st.header("1. Top & Bottom Line Growth")
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(x=years, y=rev/1e9, name="Revenue", marker_color='#3b82f6'))
                fig1.add_trace(go.Scatter(x=years, y=ni/1e9, name="Net Income", line=dict(color='#10b981', width=4)))
                fig1.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                st.plotly_chart(fig1, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Tracks total sales (Blue) against actual money kept after all expenses (Green).<br><br><b>Trend:</b> Revenue reached {fin_sym}{rev.iloc[-1]/1e9:.2f}B in the most recent year.<br><br><b>Conclusion:</b> By comparing the trajectory, we see if {name} is sacrificing profit to gain market share. A rising green line means management is scaling operations profitably without bleeding cash.</div>", unsafe_allow_html=True)

            with c2:
                st.header("2. Margin Efficiency Trajectory")
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=years, y=(gp/rev)*100, name="Gross Margin %", line=dict(color='#f59e0b', width=3)))
                fig2.add_trace(go.Scatter(x=years, y=(op_inc/rev)*100, name="Operating Margin %", line=dict(color='#8b5cf6', width=3)))
                fig2.add_trace(go.Scatter(x=years, y=(ni/rev)*100, name="Net Margin %", fill='tozeroy', line_color='#10b981'))
                fig2.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title="Percentage (%)")
                st.plotly_chart(fig2, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Margins measure operational efficiency. Gross is after manufacturing, Operating is after overhead, Net is after taxes.<br><br><b>Trend:</b> The final net margin shifted to {(ni.iloc[-1]/rev.iloc[-1])*100:.1f}% this year.<br><br><b>Conclusion:</b> The gap between Gross (Orange) and Operating (Purple) is what they spend on administration. A stable green area proves strong pricing power.</div>", unsafe_allow_html=True)

            c3, c4 = st.columns(2)
            with c3:
                st.header("3. Quality of Earnings")
                fig3 = go.Figure()
                fig3.add_trace(go.Bar(x=years, y=ni/1e9, name="Net Income", marker_color='#64748b'))
                fig3.add_trace(go.Bar(x=years, y=ocf/1e9, name="Operating Cash Flow", marker_color='#14b8a6'))
                fig3.update_layout(template="plotly_dark", height=350, barmode='group', margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                st.plotly_chart(fig3, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Net Income is easily manipulated by accounting rules. Operating Cash Flow is the physical money hitting the bank.<br><br><b>Trend:</b> Cash Flow sits at {fin_sym}{ocf.iloc[-1]/1e9:.2f}B vs Net Income of {fin_sym}{ni.iloc[-1]/1e9:.2f}B.<br><br><b>Conclusion:</b> Because cash flow is {'higher' if ocf.iloc[-1]>ni.iloc[-1] else 'lower'} than paper profits, the earnings are backed by true liquidity. High-quality businesses routinely show higher operating cash than net income.</div>", unsafe_allow_html=True)

            with c4:
                st.header("4. CapEx & Free Cash Flow")
                fig4 = go.Figure()
                fig4.add_trace(go.Bar(x=years, y=ocf/1e9, name="Cash Generated", marker_color='#3b82f6'))
                fig4.add_trace(go.Bar(x=years, y=-capex/1e9, name="CapEx", marker_color='#ef4444'))
                fig4.add_trace(go.Scatter(x=years, y=fcf/1e9, name="Free Cash Flow", line=dict(color='#10b981', width=4)))
                fig4.update_layout(template="plotly_dark", height=350, barmode='relative', margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                st.plotly_chart(fig4, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> CapEx (Red) is money reinvested into physical assets. Free Cash Flow (Green) is what remains for shareholders.<br><br><b>Trend:</b> Reinvestment required {fin_sym}{capex.iloc[-1]/1e9:.2f}B this year.<br><br><b>Conclusion:</b> The green line represents the true value of the business. Generating {fin_sym}{fcf.iloc[-1]/1e9:.2f}B in pure free cash gives management massive power to buy back stock, acquire competitors, or pay dividends.</div>", unsafe_allow_html=True)

            c5, c6 = st.columns(2)
            with c5:
                st.header("5. Short-Term Liquidity")
                if is_bank or not has_wc_data:
                    fig5 = go.Figure(go.Scatter(x=years, y=[0]*len(years), mode='lines', line=dict(color='#374151')))
                    fig5.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title="Ratio")
                    st.plotly_chart(fig5, use_container_width=True)
                    st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> The Current Ratio measures if the company has enough liquid assets to pay debts due within 12 months.<br><br><b>Trend:</b> Data Unavailable.<br><br><b>Conclusion:</b> Current/Non-Current asset categorization is structurally inapplicable or unavailable for this ticker in standard financial feeds.</div>", unsafe_allow_html=True)
                else:
                    cr = np.where(curr_liab == 0, 0, curr_assets / curr_liab)
                    fig5 = go.Figure(go.Scatter(x=years, y=cr, mode='lines+markers', line=dict(color='#facc15', width=4)))
                    fig5.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title="Ratio")
                    st.plotly_chart(fig5, use_container_width=True)
                    st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> The Current Ratio measures if the company has enough liquid assets to pay debts due within 12 months.<br><br><b>Trend:</b> The ratio stabilized at {cr[-1]:.2f}x.<br><br><b>Conclusion:</b> A ratio above 1.0 indicates adequate liquidity to survive the year without external bridging.</div>", unsafe_allow_html=True)

            with c6:
                st.header("6. Long-Term Solvency")
                fig6 = go.Figure()
                fig6.add_trace(go.Bar(x=years, y=equity/1e9, name="Equity", marker_color='#10b981'))
                fig6.add_trace(go.Bar(x=years, y=debt/1e9, name="Debt", marker_color='#ef4444'))
                fig6.update_layout(template="plotly_dark", height=350, barmode='group', margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                st.plotly_chart(fig6, use_container_width=True)
                if is_bank:
                    st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Shareholder Equity vs. Corporate Debt.<br><br><b>Trend:</b> N/A Corporate Debt for Banks.<br><br><b>Conclusion:</b> Financial institutions utilize customer deposits as their primary leverage rather than standard corporate debt. Therefore, debt bars are structurally zero or minimal.</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> A direct visual comparison of shareholder money (Green) vs. borrowed bank money (Red).<br><br><b>Trend:</b> Total corporate debt is {fin_sym}{debt.iloc[-1]/1e9:.2f}B.<br><br><b>Conclusion:</b> The Debt-to-Equity ratio reveals the firm's leverage profile. Less reliance on red bars means the company is self-funded and highly resilient to macroeconomic shocks.</div>", unsafe_allow_html=True)

            c7, c8 = st.columns(2)
            with c7:
                st.header("7. EBITDA Trajectory")
                fig7 = go.Figure(go.Bar(x=years, y=ebitda/1e9, marker_color='#8b5cf6'))
                fig7.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                st.plotly_chart(fig7, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> EBITDA stands for Earnings Before Interest, Taxes, Depreciation, and Amortization.<br><br><b>Trend:</b> Core operational profit reached {fin_sym}{ebitda.iloc[-1]/1e9:.2f}B.<br><br><b>Conclusion:</b> This strips away accounting depreciation and taxes to show the raw, pure engine of the business before external factors.</div>", unsafe_allow_html=True)

            with c8:
                st.header("8. Debt Servicing (Interest Coverage)")
                icr = op_inc / interest
                fig8 = go.Figure(go.Scatter(x=years, y=icr, fill='tozeroy', line_color='#ec4899'))
                fig8.add_hline(y=1.5, line_dash="dash", line_color="red")
                fig8.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title="Ratio")
                st.plotly_chart(fig8, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Shows how many times over the company can pay the interest on its debt using its operating profit.<br><br><b>Trend:</b> The ratio is currently {icr.iloc[-1]:.1f}x.<br><br><b>Conclusion:</b> {name} generates {icr.iloc[-1]:.1f}x more operating profit than it needs to pay its bankers. Lenders view anything above the red line as safe.</div>", unsafe_allow_html=True)

            c9, c10 = st.columns(2)
            with c9:
                st.header("9. Return on Assets & Equity")
                fig9 = go.Figure()
                fig9.add_trace(go.Scatter(x=years, y=(ni/assets)*100, name="ROA %", line=dict(color='#06b6d4', width=3)))
                fig9.add_trace(go.Scatter(x=years, y=(ni/equity)*100, name="ROE %", line=dict(color='#3b82f6', width=3)))
                fig9.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title="Percentage (%)")
                st.plotly_chart(fig9, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> ROA (Teal) shows profit generated from total assets. ROE (Blue) shows profit generated specifically from shareholder money.<br><br><b>Trend:</b> ROE stands at {(ni.iloc[-1]/equity.iloc[-1])*100:.1f}%.<br><br><b>Conclusion:</b> This proves how effectively management is compounding investor capital. A rising blue line is the ultimate goal for shareholders.</div>", unsafe_allow_html=True)

            with c10:
                st.header("10. Net Working Capital")
                if is_bank or not has_wc_data:
                    fig10 = go.Figure(go.Bar(x=years, y=[0]*len(years), marker_color='#374151'))
                    fig10.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                    st.plotly_chart(fig10, use_container_width=True)
                    st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Current Assets minus Current Liabilities.<br><br><b>Trend:</b> Data Unavailable.<br><br><b>Conclusion:</b> Metrics are structurally inapplicable or explicitly missing for this specific ticker.</div>", unsafe_allow_html=True)
                else:
                    nwc = curr_assets - curr_liab
                    fig10 = go.Figure(go.Bar(x=years, y=nwc/1e9, marker_color=np.where(nwc>0, '#10b981', '#ef4444')))
                    fig10.update_layout(template="plotly_dark", height=350, margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                    st.plotly_chart(fig10, use_container_width=True)
                    st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Current Assets minus Current Liabilities. This measures the short-term liquidity runway.<br><br><b>Trend:</b> Working Capital sits at {fin_sym}{nwc.iloc[-1]/1e9:.2f}B.<br><br><b>Conclusion:</b> A positive (Green) number gives the company massive flexibility to fund daily operations without taking loans. Red indicates a potential cash crunch.</div>", unsafe_allow_html=True)

            c11, c12 = st.columns(2)
            with c11:
                st.header("11. Cost Structure (The Revenue Dollar)")
                cogs = rev.iloc[-1] - gp.iloc[-1]
                opex = gp.iloc[-1] - op_inc.iloc[-1]
                taxes_other = op_inc.iloc[-1] - ni.iloc[-1]
                
                raw_values = [max(0, cogs), max(0, opex), max(0, taxes_other), max(0, ni.iloc[-1])]
                labels = ['Cost of Goods', 'Operating Expenses', 'Taxes/Other', 'Net Profit Retained']
                formatted_text = [format_kmb(v) for v in raw_values]

                fig11 = go.Figure(go.Pie(
                    labels=labels, values=raw_values, hole=0.4,
                    marker_colors=['#f59e0b', '#8b5cf6', '#ef4444', '#10b981'],
                    textinfo='percent', hovertext=formatted_text, hoverinfo='label+text+percent' 
                ))
                fig11.update_layout(
                    template="plotly_dark", height=350, margin=dict(b=0, t=30),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig11, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Concept:</b> Breaks down exactly where every dollar of {years[-1]} revenue went.<br><br><b>Trend:</b> The green slice represents the final {(ni.iloc[-1]/rev.iloc[-1])*100:.1f}% kept as profit.<br><br><b>Conclusion:</b> This visualizes the company's cost burden. A larger green slice relative to orange and purple indicates a highly efficient business model.</div>", unsafe_allow_html=True)
            with c12:
                st.header("12. Asset vs. Liability Composition")
                fig12 = go.Figure()
                fig12.add_trace(go.Bar(x=years, y=assets/1e9, name="Total Assets", marker_color='#3b82f6'))
                fig12.add_trace(go.Bar(x=years, y=liab/1e9, name="Total Liabilities", marker_color='#ef4444'))
                fig12.update_layout(template="plotly_dark", height=350, barmode='group', margin=dict(b=0), xaxis_title="Fiscal Year", yaxis_title=f"Amount ({fin_sym} Billions)")
                st.plotly_chart(fig12, use_container_width=True)
                st.markdown(f"<div class='conclusion-box'><b>Agenda:</b> Compares everything the company owns (Assets) against everything it owes (Liabilities).<br><br><b>Trend:</b> Total Assets reached {fin_sym}{assets.iloc[-1]/1e9:.2f}B.<br><br><b>Conclusion:</b> As long as the Blue bars grow faster than the Red bars, the company is building intrinsic equity value and increasing its net worth.</div>", unsafe_allow_html=True)

            st.markdown("<div class='custom-line'></div>", unsafe_allow_html=True)
            st.header("13. Traditional M&A & Capital Velocity")

            acquisitions = cf.get('Net Business Purchase And Sale', pd.Series([0]*len(cf))).iloc[:slice_idx][::-1].fillna(0).abs()
            total_investment = cf.get('Investing Cash Flow', rev * -0.1).iloc[:slice_idx][::-1].fillna(0).abs()

            m1, m2 = st.columns([1, 2])

            with m1:
                st.markdown("### M&A Strategic Summary")
                avg_acquisition_spend = acquisitions.mean() / 1e9
                intensity_ratio = (acquisitions.sum() / total_investment.sum()) * 100 if total_investment.sum() != 0 else 0
                
                st.write(f"""
                This section monitors the **Inorganic Growth Engine**. By analyzing traditional M&A data, we track how aggressively {name} is buying market share.
                
                - **Avg. Annual Acquisition Spend:** {sym}{avg_acquisition_spend:.2f}B
                - **Capital Reinvestment Intensity:** {intensity_ratio:.1f}%
                """)
                
                if intensity_ratio > 30:
                    st.info("💡 **Strategy Note:** High M&A Intensity. The company is in an 'Aggressive Consolidator' phase.")
                else:
                    st.info("💡 **Strategy Note:** Low M&A Intensity. Growth is currently driven by internal R&D and organic operations.")

            with m2:
                fig13 = go.Figure()
                fig13.add_trace(go.Scatter(x=years, y=total_investment/1e9, name="Total Investing Outlay", fill='tonexty', line_color='#6366f1'))
                fig13.add_trace(go.Bar(x=years, y=acquisitions/1e9, name="M&A Spend", marker_color='#f59e0b'))
                
                fig13.update_layout(
                    template="plotly_dark", height=400, margin=dict(b=0),
                    yaxis_title=f"Amount in {sym} Billions",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig13, use_container_width=True)

            st.markdown(f"<div class='conclusion-box'><b>Concept:</b> Compares total capital invested (Purple) against specific M&A acquisitions (Orange).<br><br><b>Trend:</b> M&A activity reached {sym}{acquisitions.iloc[-1]/1e9:.2f}B this period.<br><br><b>Conclusion:</b> Monitoring the gap between these two figures reveals if the company is growing through synergy (buying others) or execution (building internally).</div>", unsafe_allow_html=True)
            
            # --- MASSIVE AUTOMATED PDF REPORT & EXCEL EXPORT ---
            st.divider()
            st.header("IN DEAPTH ANALYTICS")
            st.write("Download the comprehensive multi-page narrative report or the raw Excel financial model.")
            c_exp1, c_exp2 = st.columns(2)
        
            def generate_deep_pdf():
                sentiment_tag = "NEUTRAL" 
                if "BULLISH" in nlp_text: sentiment_tag = "BULLISH"
                elif "BEARISH" in nlp_text: sentiment_tag = "BEARISH"

                roe_val = info.get('returnOnEquity', 0) * 100
                try:
                    raw_equity = bs['Stockholders Equity'].iloc[-1]
                    safe_equity = 0 if pd.isna(raw_equity) else (raw_equity / 1e9)
                except:
                    safe_equity = 0

                equity_val = bs.get('Stockholders Equity', pd.Series([0])).iloc[-1]
                if pd.isna(equity_val): equity_val = 0
                
                is_positive = ni.iloc[-1] > 0
                fcf_is_positive = fcf.iloc[-1] > 0

                health_status = "robust operational integrity" if is_positive else "significant operational challenges"
                sustainability_msg = "The gap between cash made and what is needed shows great long-term health." if is_positive else "The gap between cash coming in and rising bills shows serious risks for the business."
                management_msg = "management is putting cash into projects that grow the business." if is_positive else "management is struggling to keep the business profitable against high costs."
                final_action = "buy other companies or reward shareholders with extra dividends." if is_positive else "focus on cutting debt and saving cash to keep the business running."

                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.multi_cell(0, 10, f"FINANCIAL RESEARCH BREAKDOWN: {name.upper()}", align='C')
                
                pdf.set_font("Arial", 'I', 10)
                pdf.cell(0, 10, f"Market Price: {pdf_sym}{price:,.2f} | Consensus Target: {pdf_sym}{intrinsic_val:,.2f} | Base Currency: {currency_code}", ln=True, align='C')
                
                pdf.line(10, 32, 200, 32)
                pdf.ln(12)
                
                if isinstance(nlp_text, tuple): safe_nlp = clean_for_pdf(nlp_text[0])
                else: safe_nlp = clean_for_pdf(nlp_text)
                safe_consensus = clean_for_pdf(consensus_text)
                
                sentiment_interpretation = f"What does the sentiment mean? The NLP engine found a {sentiment_tag} mood in the news. This means the latest stories are highlighting growth chances or risks that aren't fully shown in the stock price yet. This helps investors see if the stock has a safety net or if it might keep falling."
                financial_interpretation = f"What does the financial health mean? With a ROE of {roe_val:.2f}%, {management_msg} For anyone reading this, it shows whether the company is actually building value or just using up its resources to stay afloat."
                
                sections = {
                    "1. Executive Summary & Intrinsic Valuation": f"This document provides a comprehensive financial breakdown of {name}. The asset is currently trading at a market price of {pdf_sym}{price:,.2f}. Based on alternative data and Wall Street consensus, the intrinsic target price is modeled at {pdf_sym}{intrinsic_val:,.2f}. Our analysis strips away standard accounting noise to focus on operational cash flow, capital structure, and true margin efficiency to determine the long-term viability of the underlying business model.",
                    "2. AI Sentiment & NLP Insights": f"{safe_nlp}",
                    "3. Consensus Forensic Breakdown": f"{safe_consensus}",
                    "4. Top-Line Trajectory & Margin Efficiency": f"Growth metrics over the observed {slice_idx}-year period reveal that total revenue successfully scaled to {pdf_sym}{rev.iloc[-1]/1e9:.2f} Billion. This top-line growth is supported by a gross margin of {(gp.iloc[-1]/rev.iloc[-1])*100:.1f}%. By managing their office and daily costs, the firm secured an operating margin of {(op_inc.iloc[-1]/rev.iloc[-1])*100:.1f}%. After all taxes, the final profit margin left for shareholders is {(ni.iloc[-1]/rev.iloc[-1])*100:.1f}%.",
                    "5. Earnings Quality Forensics": f"Real cash (Operating Cash Flow) is harder to fake than paper profits. This analysis shows {name} produced {pdf_sym}{ocf.iloc[-1]/1e9:.2f} Billion in actual cash. Since this cash amount is {'higher' if ocf.iloc[-1]>ni.iloc[-1] else 'lower'} than the reported profit of {pdf_sym}{ni.iloc[-1]/1e9:.2f} Billion, we can see how honest and strong their accounting really is.",
                    "6. Capital Reinvestment (CapEx) & Free Cash Flow": f"To keep the business running and growing, the company spent {pdf_sym}{capex.iloc[-1]/1e9:.2f} Billion on equipment and upgrades. After paying for these, the leftover 'Free Cash Flow' is {pdf_sym}{fcf.iloc[-1]/1e9:.2f} Billion. This {'helps' if fcf_is_positive else 'hurts'} the company's ability to stay independent and grow without needing to borrow more money.",
                    "7. Capital Structure, Liquidity & Default Risk": f"The balance sheet shows the company has {pdf_sym}{safe_equity:.2f} Billion in value for owners against debts of {pdf_sym}{info.get('totalDebt', 0)/1e9:.2f} Billion. This tells us if the company has enough money in the bank to pay its bills over the next year without running into trouble.",
                    "8. M&A Strategic Velocity & Portfolio Impact": f"The company spends about {pdf_sym}{acquisitions.mean()/1e9:.2f}B a year buying other businesses. This M&A spending makes up {(acquisitions.sum()/total_investment.sum())*100:.1f}% of their total investment. This shows if they are growing by being better at their job or just by buying out competitors.",
                    "9. Final Strategic Verdict": f"The multi-year data confirms that {name} shows {health_status}. {sustainability_msg} \n\n{sentiment_interpretation} \n\n{financial_interpretation} \n\nIn light of these metrics, management should {final_action} as a priority to secure the company's long-term future."
                }
                
                for title, text in sections.items():
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, title, ln=True)
                    pdf.set_font("Arial", '', 11)
                    pdf.multi_cell(0, 6, text.encode('latin-1', 'replace').decode('latin-1'))
                    pdf.ln(8)
                    
                return pdf.output(dest="S").encode("latin-1")

            def generate_excel():
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_formatted = pd.DataFrame({
                        'Revenue': rev.apply(lambda x: fin_sym + format_kmb(x).replace('$', '')),
                        'Net Income': ni.apply(lambda x: fin_sym + format_kmb(x).replace('$', '')),
                        'Operating Cash Flow': ocf.apply(lambda x: fin_sym + format_kmb(x).replace('$', '')),
                        'CapEx': capex.apply(lambda x: fin_sym + format_kmb(x).replace('$', '')),
                        'Free Cash Flow (UFCF)': fcf.apply(lambda x: fin_sym + format_kmb(x).replace('$', '')),
                        'Total Equity': equity.apply(lambda x: fin_sym + format_kmb(x).replace('$', '')),
                        'Total Debt': debt.apply(lambda x: fin_sym + format_kmb(x).replace('$', ''))
                    })
                    
                    df_raw = pd.DataFrame({
                        'Revenue': rev/1e9, 
                        'Gross Profit': gp/1e9,
                        'Net Income': ni/1e9,
                        'Op Cash Flow': ocf/1e9,
                        'CapEx': capex/1e9,
                        'Free Cash Flow': fcf/1e9,
                        'Total Equity': equity/1e9,
                        'Total Debt': debt/1e9
                    })
                    
                    df_formatted.to_excel(writer, sheet_name='Financial Model')
                    df_raw.to_excel(writer, sheet_name='Chart Data')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Financial Model']
                    max_row = len(years) + 1

                    chart1 = workbook.add_chart({'type': 'column'})
                    chart1.add_series({'name': "='Chart Data'!$B$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$B$2:$B${max_row}", 'fill': {'color': '#3b82f6'}})
                    chart1.add_series({'name': "='Chart Data'!$D$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$D$2:$D${max_row}", 'fill': {'color': '#10b981'}})
                    chart1.set_title({'name': f'Revenue vs Net Income ({fin_sym} Billions)'})
                    worksheet.insert_chart('J2', chart1)

                    chart2 = workbook.add_chart({'type': 'column'})
                    chart2.add_series({'name': "='Chart Data'!$E$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$E$2:$E${max_row}", 'fill': {'color': '#14b8a6'}})
                    chart2.add_series({'name': "='Chart Data'!$F$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$F$2:$F${max_row}", 'fill': {'color': '#ef4444'}})
                    chart2.add_series({'name': "='Chart Data'!$G$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$G$2:$G${max_row}", 'type': 'line', 'line': {'color': '#10b981', 'width': 3}})
                    chart2.set_title({'name': f'Cash Flow Engine ({fin_sym} Billions)'})
                    worksheet.insert_chart('J17', chart2)

                    chart3 = workbook.add_chart({'type': 'column'})
                    chart3.add_series({'name': "='Chart Data'!$H$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$H$2:$H${max_row}", 'fill': {'color': '#10b981'}})
                    chart3.add_series({'name': "='Chart Data'!$I$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$I$2:$I${max_row}", 'fill': {'color': '#ef4444'}})
                    chart3.set_title({'name': f'Capital Structure ({fin_sym} Billions)'})
                    worksheet.insert_chart('R2', chart3)

                    chart4 = workbook.add_chart({'type': 'column'})
                    chart4.add_series({'name': "='Chart Data'!$B$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$B$2:$B${max_row}", 'fill': {'color': '#3b82f6'}})
                    chart4.add_series({'name': "='Chart Data'!$C$1", 'categories': f"='Chart Data'!$A$2:$A${max_row}", 'values': f"='Chart Data'!$C$2:$C${max_row}", 'fill': {'color': '#f59e0b'}})
                    chart4.set_title({'name': f'Revenue vs Gross Profit ({fin_sym} Billions)'})
                    worksheet.insert_chart('R17', chart4)
                    
                    df_def = pd.DataFrame({
                        'Metric': ['Revenue', 'CapEx', 'Free Cash Flow (UFCF)', 'Current Ratio', 'Debt-to-Equity'],
                        'Analyst Definition': [
                            'Total top-line sales generated by the core business.',
                            'Capital Expenditures: Money spent on buying or upgrading physical assets.',
                            'Unlevered Free Cash Flow: Pure cash left over after expenses and CapEx.',
                            'Short-term liquidity. Current Assets divided by Current Liabilities.',
                            'Total Debt divided by Shareholder Equity. Measures long-term risk.'
                        ]
                    })
                    df_def.to_excel(writer, sheet_name='Metric Guide', index=False)
                    
                return output.getvalue()

            with c_exp1:
                st.download_button("📄 Download in deapth Report (with AI Insights)", generate_deep_pdf(), file_name=f"{ticker}_Research.pdf", mime="application/pdf")
            with c_exp2:
                st.download_button("📊 Download financial data and model", generate_excel(), file_name=f"{ticker}_Model.xlsx")

        except Exception as e:
            st.error(f"Critical Error Mining Fundamental Data: {e}")
# ==========================================
        # PART 2: THE CUSTOM PRO TERMINAL (TIMEZONE & VOLUME FIXED)
        # ==========================================
        st.markdown("---") 
        st.markdown("### 📈 Market Eye")
        st.write("Decoding global liquidity through time synced volume.")

        # 1. Trading Intervals
        interval_options = {
            "1 Minute (Scalping)": ("1m", "5d"),
            "5 Minutes": ("5m", "1mo"),
            "15 Minutes": ("15m", "1mo"),
            "30 Minutes": ("30m", "1mo"),
            "1 Hour": ("1h", "1mo")
        }

        selected_interval = st.selectbox("Select Trading Interval:", list(interval_options.keys()), index=1)
        yf_interval, yf_period = interval_options[selected_interval]

        with st.spinner(f"Rendering pro-grade terminal for {ticker}..."):
            try:
                # 2. Fetch Free Intraday Data
                df_tech = yf.download(ticker, period=yf_period, interval=yf_interval, progress=False)

                if isinstance(df_tech.columns, pd.MultiIndex):
                    df_tech.columns = df_tech.columns.get_level_values(0)

                if not df_tech.empty and len(df_tech) > 50:
                    
                    # ==========================================
                    # THE TIMEZONE FIX (IST vs EST)
                    # ==========================================
                    # Make sure the data has a timezone, then convert it based on the exchange
                    if df_tech.index.tz is None:
                        df_tech.index = df_tech.index.tz_localize('UTC')
                        
                    if ticker.endswith('.NS') or ticker.endswith('.BO'):
                        df_tech.index = df_tech.index.tz_convert('Asia/Kolkata')
                    else:
                        df_tech.index = df_tech.index.tz_convert('America/New_York')

                    # 3. Calculate ALL Indicators mathematically first
                    df_tech.ta.sma(length=20, append=True) 
                    df_tech.ta.ema(length=50, append=True) 
                    df_tech.ta.bbands(length=20, std=2, append=True)
                    df_tech.ta.rsi(length=14, append=True)
                    df_tech.ta.macd(fast=12, slow=26, signal=9, append=True)
                    
                    if 'Volume' in df_tech.columns and not df_tech['Volume'].eq(0).all():
                        df_tech.ta.vwap(append=True)
                        has_vwap = True
                    else:
                        has_vwap = False

                    df_tech.dropna(inplace=True)

                    # Create color array for Volume bars (Green for up, Red for down)
                    colors = ['#10b981' if row['Close'] >= row['Open'] else '#ef4444' for index, row in df_tech.iterrows()]

                    # 4. Build the Plotly Multi-Pane Chart (NOW 4 ROWS FOR VOLUME)
                    fig_tech = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                                        vertical_spacing=0.02, 
                                        row_heights=[0.5, 0.15, 0.15, 0.2], # Optimized heights
                                        subplot_titles=("Price Action & Overlays", "Volume", "MACD Momentum", "RSI (14)"))

                    # --- ROW 1: Price & Overlays ---
                    fig_tech.add_trace(go.Candlestick(x=df_tech.index, open=df_tech['Open'], high=df_tech['High'], low=df_tech['Low'], close=df_tech['Close'], name="Price"), row=1, col=1)
                    
                    sma_col = df_tech.columns[df_tech.columns.str.contains('SMA_')][0]
                    ema_col = df_tech.columns[df_tech.columns.str.contains('EMA_')][0]
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[sma_col], line=dict(color='#facc15', width=1.5), name="20 SMA"), row=1, col=1)
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[ema_col], line=dict(color='#3b82f6', width=1.5), name="50 EMA"), row=1, col=1)
                    
                    if has_vwap:
                        vwap_col = df_tech.columns[df_tech.columns.str.startswith('VWAP')][0]
                        fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[vwap_col], line=dict(color='#ec4899', width=2, dash='dot'), name="VWAP"), row=1, col=1)

                    bb_upper = df_tech.columns[df_tech.columns.str.contains('BBU_')][0]
                    bb_lower = df_tech.columns[df_tech.columns.str.contains('BBL_')][0]
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[bb_upper], line=dict(color='gray', width=1, dash='dot'), name="BB Upper"), row=1, col=1)
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[bb_lower], line=dict(color='gray', width=1, dash='dot'), name="BB Lower", fill='tonexty', fillcolor='rgba(128,128,128,0.05)'), row=1, col=1)

                    # --- ROW 2: VOLUME (NEW) ---
                    fig_tech.add_trace(go.Bar(x=df_tech.index, y=df_tech['Volume'], marker_color=colors, name="Volume"), row=2, col=1)

                    # --- ROW 3: MACD ---
                    macd_line = df_tech.columns[df_tech.columns.str.startswith('MACD_')][0]
                    macd_signal = df_tech.columns[df_tech.columns.str.startswith('MACDs_')][0]
                    macd_hist = df_tech.columns[df_tech.columns.str.startswith('MACDh_')][0]
                    
                    fig_tech.add_trace(go.Bar(x=df_tech.index, y=df_tech[macd_hist], marker_color=np.where(df_tech[macd_hist]>=0, '#10b981', '#ef4444'), name="Histogram"), row=3, col=1)
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[macd_line], line=dict(color='#3b82f6', width=1.5), name="MACD"), row=3, col=1)
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[macd_signal], line=dict(color='#f97316', width=1.5), name="Signal"), row=3, col=1)

                    # --- ROW 4: RSI ---
                    rsi_col = df_tech.columns[df_tech.columns.str.contains('RSI_')][0]
                    fig_tech.add_trace(go.Scatter(x=df_tech.index, y=df_tech[rsi_col], line=dict(color='#c084fc', width=1.5), name="RSI"), row=4, col=1)
                    fig_tech.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
                    fig_tech.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

                    # ==========================================
                    # 5. THE PERFECT ZOOM & SQUISH FIX (FOR ALL ROWS)
                    # ==========================================
                    if yf_interval == "1m": zoom_candles = 60
                    elif yf_interval == "5m": zoom_candles = 50
                    elif yf_interval == "15m": zoom_candles = 40
                    elif yf_interval == "30m": zoom_candles = 30
                    else: zoom_candles = 90
                    zoom_candles = min(zoom_candles, len(df_tech))

                    x_start, x_end = df_tech.index[-zoom_candles], df_tech.index[-1]
                    visible_data = df_tech.iloc[-zoom_candles:]

                    # Calculate precise Y-axis bounds for EVERY subplot based only on visible data
                    y_min, y_max = visible_data['Low'].min(), visible_data['High'].max()
                    y_pad = (y_max - y_min) * 0.05 
                    
                    vol_max = visible_data['Volume'].max() * 1.1 # 10% padding above volume
                    
                    macd_min = visible_data[[macd_line, macd_signal, macd_hist]].min().min()
                    macd_max = visible_data[[macd_line, macd_signal, macd_hist]].max().max()
                    macd_pad = abs(macd_max - macd_min) * 0.1

                    # Force the camera zoom on X-axis
                    fig_tech.update_xaxes(range=[x_start, x_end])
                    
                    # Force the Auto-Scale on ALL Y-axes
                    fig_tech.update_yaxes(range=[y_min - y_pad, y_max + y_pad], row=1, col=1) # Price
                    fig_tech.update_yaxes(range=[0, vol_max], row=2, col=1)                   # Volume
                    fig_tech.update_yaxes(range=[macd_min - macd_pad, macd_max + macd_pad], row=3, col=1) # MACD

                    # Hide weekend gaps
                    fig_tech.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

                    fig_tech.update_layout(
                        height=900, 
                        template="plotly_dark",
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        xaxis_rangeslider_visible=False,
                        margin=dict(l=10, r=10, t=50, b=10)
                    )
                    
                    st.plotly_chart(fig_tech, use_container_width=True)

                    # 6. The AI Confluence Matrix
                    latest_rsi = df_tech[rsi_col].iloc[-1]
                    latest_close = df_tech['Close'].iloc[-1]
                    latest_sma = df_tech[sma_col].iloc[-1]
                    
                    st.markdown("### 🤖 Technical Matrix")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if latest_rsi > 70: st.error(f"**RSI ({latest_rsi:.1f}):** Overbought (Bearish)")
                        elif latest_rsi < 30: st.success(f"**RSI ({latest_rsi:.1f}):** Oversold (Bullish)")
                        else: st.info(f"**RSI ({latest_rsi:.1f}):** Neutral")
                            
                    with col2:
                        if latest_close > latest_sma: st.success(f"**Trend:** Bullish (Above 20 SMA)")
                        else: st.error(f"**Trend:** Bearish (Below 20 SMA)")
                            
                    with col3:
                        if has_vwap:
                            latest_vwap = df_tech[vwap_col].iloc[-1]
                            if latest_close > latest_vwap: st.success(f"**Intraday:** Bullish (Above VWAP)")
                            else: st.error(f"**Intraday:** Bearish (Below VWAP)")
                        else:
                            st.warning("**Note:** Chart is powered by custom yfinance data. AI calculates momentum underneath.")

            except Exception as e:
                st.error(f"Engine logic error: {e}")

# Put this right above your charting code
if st.button("🔄 Refresh Live Data"):
    st.rerun() # This forces Streamlit to re-download the latest yfinance data
