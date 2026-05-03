import yfinance as yf
import pandas as pd

def fetch_financial_statements(ticker_symbol):
    print(f"[{ticker_symbol}] Fetching financial data from API...")
    try:
        stock = yf.Ticker(ticker_symbol)
        income_stmt = stock.financials.T
        balance_sheet = stock.balance_sheet.T
        cash_flow = stock.cashflow.T
        
        if income_stmt.empty or balance_sheet.empty or cash_flow.empty:
            print(f"[{ticker_symbol}] Warning: Incomplete data found.")
            return None, None, None
            
        print(f"[{ticker_symbol}] Data successfully ingested.")
        return income_stmt, balance_sheet, cash_flow

    except Exception as e:
        print(f"[{ticker_symbol}] Error fetching data: {e}")
        return None, None, None

def get_best_match(df, possible_columns):
    for col in possible_columns:
        if col in df.columns:
            return df[col]
    return 0
import yfinance as yf

def get_dupont_and_health_metrics(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        # --- FALLBACK CALCULATION LOGIC ---
        try:
            # Pull raw data from statements
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            
            latest_ni = financials.loc['Net Income'].iloc[0]
            latest_rev = financials.loc['Total Revenue'].iloc[0]
            latest_assets = balance_sheet.loc['Total Assets'].iloc[0]
            latest_equity = balance_sheet.loc['Stockholders Equity'].iloc[0]

            # Manual Calculations
            calc_roe = (latest_ni / latest_equity) * 100 if latest_equity != 0 else 0
            calc_roa = (latest_ni / latest_assets) * 100 if latest_assets != 0 else 0
            calc_margin = (latest_ni / latest_rev) * 100 if latest_rev != 0 else 0
        except:
            calc_roe = calc_roa = calc_margin = 0

        # --- DATA ASSIGNMENT ---
        # Use calculated values if the API .info data is missing (zero)
        roe = calc_roe if calc_roe != 0 else info.get('returnOnEquity', 0) * 100
        roa = calc_roa if calc_roa != 0 else info.get('returnOnAssets', 0) * 100
        margins = calc_margin if calc_margin != 0 else info.get('profitMargins', 0) * 100
        
        
        output = f"• <b>Return on Equity (ROE):</b> {roe:.2f}%<br>"
        output += f"• <b>Return on Assets (ROA):</b> {roa:.2f}%<br>"
        output += f"• <b>Net Margins:</b> {margins:.2f}%<br><br>"
        
        # The Verdict logic stays the same
        if roe > 15: 
            output += "<b>Verdict:</b> Strong capital compounding. Management is highly efficient."
        elif roe > 0: 
            output += "<b>Verdict:</b> Average efficiency. Watch for rising debt loads."
        else: 
            output += "<b>Verdict:</b> Negative returns. Core business is currently destroying equity value."
            
        return output
    except Exception as e:
        return f"Error analyzing data: {e}"

def clean_financial_data(ticker_symbol, inc, bs, cf):
    print(f"[{ticker_symbol}] Standardizing accounting data...")
    clean_df = pd.DataFrame(index=inc.index)
    
    try:
        clean_df['Revenue'] = get_best_match(inc, ['Total Revenue', 'Operating Revenue', 'Revenue'])
        clean_df['EBIT'] = get_best_match(inc, ['Operating Income', 'EBIT'])
        clean_df['Net Income'] = get_best_match(inc, ['Net Income', 'Net Income Common Stockholders'])
        clean_df['Interest Expense'] = get_best_match(inc, ['Interest Expense', 'Interest Expense Non Operating'])
        clean_df['Tax Provision'] = get_best_match(inc, ['Tax Provision', 'Income Tax Expense'])
        
        clean_df['Total Cash'] = get_best_match(bs, ['Cash And Cash Equivalents', 'Cash', 'Cash Cash Equivalents And Short Term Investments'])
        clean_df['Total Debt'] = get_best_match(bs, ['Total Debt', 'Long Term Debt'])
        clean_df['Current Assets'] = get_best_match(bs, ['Current Assets', 'Total Current Assets'])
        clean_df['Current Liabilities'] = get_best_match(bs, ['Current Liabilities', 'Total Current Liabilities'])
        
        clean_df['NWC'] = clean_df['Current Assets'] - clean_df['Current Liabilities']
        
        clean_df['D&A'] = get_best_match(cf, ['Depreciation And Amortization', 'Depreciation'])
        clean_df['CapEx'] = get_best_match(cf, ['Capital Expenditure', 'Investments In Property Plant And Equipment']) 
        
        print(f"[{ticker_symbol}] Standardization complete.")
        return clean_df
        
    except Exception as e:
        print(f"[{ticker_symbol}] Error during standardization: {e}")
        return None

def calculate_fcf(clean_df):
    print("Calculating Unlevered Free Cash Flow (UFCF)...")
    df = clean_df.sort_index(ascending=True).copy()
    
    df['Tax Rate'] = df['Tax Provision'] / df['EBIT']
    df['NOPAT'] = df['EBIT'] * (1 - df['Tax Rate'])
    df['Delta NWC'] = df['NWC'].diff().fillna(0)
    df['UFCF'] = df['NOPAT'] + df['D&A'] + df['CapEx'] - df['Delta NWC']
    
    print("FCF Math complete.")
    return df

def fetch_macro_data(ticker_symbol):
    print(f"[{ticker_symbol}] Fetching live macroeconomic data for WACC...")
    try:
        tnx = yf.Ticker("^TNX")
        risk_free_rate = tnx.history(period="1d")['Close'].iloc[-1] / 100
        
        stock = yf.Ticker(ticker_symbol)
        beta = stock.info.get('beta', 1.0)
        market_cap = stock.info.get('marketCap', 0)
        
        print(f"[{ticker_symbol}] Macro data secured. Risk-Free Rate: {risk_free_rate:.2%}, Beta: {beta}")
        return risk_free_rate, beta, market_cap

    except Exception as e:
        print(f"[{ticker_symbol}] Error fetching macro data: {e}")
        return 0.045, 1.0, 0
    
def calculate_wacc(ticker_symbol, clean_df, risk_free_rate, beta, market_cap):
    print(f"[{ticker_symbol}] Calculating Weighted Average Cost of Capital (WACC)...")
    market_risk_premium = 0.055
    cost_of_equity = risk_free_rate + (beta * market_risk_premium)
    
    latest_data = clean_df.sort_index(ascending=True).iloc[-1]
    total_debt = latest_data['Total Debt']
    interest_expense = latest_data['Interest Expense']
    
    cost_of_debt = (interest_expense / total_debt) if total_debt > 0 else 0
    tax_rate = latest_data['Tax Provision'] / latest_data['EBIT']
    
    total_value = market_cap + total_debt
    weight_equity = market_cap / total_value
    weight_debt = total_debt / total_value
    
    wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt * (1 - tax_rate))
    
    print(f"[{ticker_symbol}] WACC Calculation Complete: {wacc:.2%}")
    return wacc, cost_of_equity, weight_equity

def project_future_cash_flows(ticker_symbol, fcf_data):
    print(f"[{ticker_symbol}] Projecting Free Cash Flows (Level 1: Consensus Mode)...")
    
    # LEVEL 1 UPGRADE: Fetch Wall Street Consensus Growth
    try:
        stock = yf.Ticker(ticker_symbol)
        # Pulls the analyst consensus revenue growth rate
        projected_growth = stock.info.get('revenueGrowth')
        
        if projected_growth is not None:
            print(f"[{ticker_symbol}] ➔ ACTIVE: Wall Street Consensus Growth Rate: {projected_growth:.2%}")
        else:
            raise ValueError("Consensus data missing from API.")
            
    except Exception as e:
        # Fallback to Level 0 logic if the API doesn't have analyst coverage for this stock
        projected_growth = fcf_data['Revenue'].pct_change().mean()
        print(f"[{ticker_symbol}] ➔ FALLBACK: Using Historical Growth Rate: {projected_growth:.2%}")

    ebit_margin = (fcf_data['EBIT'] / fcf_data['Revenue']).mean()
    tax_rate = fcf_data['Tax Rate'].mean()
    capex_margin = (fcf_data['CapEx'] / fcf_data['Revenue']).mean()
    da_margin = (fcf_data['D&A'] / fcf_data['Revenue']).mean()
    nwc_margin = (fcf_data['NWC'] / fcf_data['Revenue']).mean()
    
    future_years = [2026, 2027, 2028, 2029, 2030]
    future_df = pd.DataFrame(index=future_years)
    
    last_revenue = fcf_data['Revenue'].iloc[-1]
    last_nwc = fcf_data['NWC'].iloc[-1]
    
    revenues = []
    for i in range(1, 6):
        # We use the Wall Street consensus to grow the revenue
        next_rev = last_revenue * ((1 + projected_growth) ** i)
        revenues.append(next_rev)
        
    future_df['Revenue'] = revenues
    future_df['EBIT'] = future_df['Revenue'] * ebit_margin
    future_df['Tax Provision'] = future_df['EBIT'] * tax_rate
    future_df['NOPAT'] = future_df['EBIT'] - future_df['Tax Provision']
    
    future_df['D&A'] = future_df['Revenue'] * da_margin
    future_df['CapEx'] = future_df['Revenue'] * capex_margin
    
    future_nwc = future_df['Revenue'] * nwc_margin
    nwc_series = pd.concat([pd.Series([last_nwc]), future_nwc])
    future_df['Delta NWC'] = nwc_series.diff().dropna().values
    
    future_df['UFCF'] = future_df['NOPAT'] + future_df['D&A'] + future_df['CapEx'] - future_df['Delta NWC']
    
    print(f"[{ticker_symbol}] 5-Year Consensus Projection Complete.")
    return future_df

def calculate_intrinsic_value(ticker_symbol, future_fcf, wacc, clean_df):
    print(f"[{ticker_symbol}] Calculating Present Value and Intrinsic Share Price...")
    
    perpetual_growth_rate = 0.025 
    final_year_fcf = future_fcf['UFCF'].iloc[-1]
    
    terminal_value = (final_year_fcf * (1 + perpetual_growth_rate)) / (wacc - perpetual_growth_rate)
    
    present_values = []
    for i, (year, row) in enumerate(future_fcf.iterrows(), start=1):
        pv = row['UFCF'] / ((1 + wacc) ** i)
        present_values.append(pv)
        
    pv_of_5_years = sum(present_values)
    pv_of_terminal_value = terminal_value / ((1 + wacc) ** 5)
    
    enterprise_value = pv_of_5_years + pv_of_terminal_value
    
    latest_data = clean_df.sort_index(ascending=True).iloc[-1]
    total_cash = latest_data['Total Cash']
    total_debt = latest_data['Total Debt']
    
    equity_value = enterprise_value + total_cash - total_debt
    
    try:
        stock = yf.Ticker(ticker_symbol)
        shares_outstanding = stock.info.get('sharesOutstanding', 0)
        
        if shares_outstanding > 0:
            implied_share_price = equity_value / shares_outstanding
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            
            print("\n" + "="*50)
            print(f"[{ticker_symbol}] LEVEL 1: CONSENSUS VALUATION RESULTS")
            print("="*50)
            print(f"Implied Intrinsic Value : ${implied_share_price:.2f} per share")
            print(f"Current Market Price    : ${current_price:.2f} per share")
            
            if implied_share_price > current_price:
                discount = (implied_share_price - current_price) / current_price
                print(f"Conclusion              : UNDERVALUED by {discount:.2%}")
            else:
                premium = (current_price - implied_share_price) / implied_share_price
                print(f"Conclusion              : OVERVALUED by {premium:.2%}")
            print("="*50 + "\n")
            
            return implied_share_price
    except Exception as e:
        print(f"Error fetching shares outstanding: {e}")
        return None

# --- The Interactive Engine ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print(" L1: WALL STREET CONSENSUS VALUATION ENGINE ")
    print("="*60)
    
    while True:
        user_input = input("\nEnter a stock ticker (e.g., AAPL, NVDA, TSLA) or type 'QUIT' to exit: ").strip().upper()
        
        if user_input == 'QUIT':
            print("Shutting down engine. Goodbye!")
            break
            
        if not user_input:
            continue
            
        test_ticker = user_input
        inc, bs, cf = fetch_financial_statements(test_ticker)
        
        if inc is not None:
            clean_data = clean_financial_data(test_ticker, inc, bs, cf)
            if clean_data is not None:
                fcf_data = calculate_fcf(clean_data)
                
                risk_free_rate, beta, market_cap = fetch_macro_data(test_ticker)
                if market_cap > 0:
                    wacc, cost_of_equity, weight_equity = calculate_wacc(
                        test_ticker, clean_data, risk_free_rate, beta, market_cap
                    )
                    
                    # Passing test_ticker down into the new projection function
                    future_fcf = project_future_cash_flows(test_ticker, fcf_data)
                    intrinsic_price = calculate_intrinsic_value(test_ticker, future_fcf, wacc, clean_data)
                else:
                    print(f"[{test_ticker}] Could not pull market cap. Valuation aborted.")
            else:
                print(f"[{test_ticker}] Data standardization failed. Check API.")