import streamlit as st
import yfinance as yf
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
nltk.download('vader_lexicon', quiet=True)

try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

def run_sentiment_analysis(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        news = stock.news
        if not news: return f"<b>System Sentiment:</b> ⚪ NEUTRAL <br><br><b>Top Filtered Headlines:</b><br>• No major recent news detected for {ticker_symbol}."
        
        # --- THE NLP EXPANSION NET ---
        # Safely extract company name, sector, and industry
        info = stock.info
        company_name = info.get('shortName', ticker_symbol).split()[0].lower()
        sector = info.get('sector', '').lower()
        industry = info.get('industry', '').lower()
        ticker_lower = ticker_symbol.lower()
        
        analyzer = SentimentIntensityAnalyzer()
        scores = []
        valid_articles = []
        
        for article in news:
            title = article.get('title', '')
            if not title and 'content' in article: 
                title = article['content'].get('title', '')
            if not title: continue 
                
            title_lower = title.lower()
            
            # The Advanced Financial Filter
            valid_keywords = [
                ticker_lower, company_name, 
                'growth', 'expansion', 'acquisition', 'm&a', 'merger', 'strategy', 'partnership',
                'earnings', 'revenue', 'profit', 'margin', 'dividend', 'guidance', 'forecast', 'ebitda',
                'demand', 'supply', 'production', 'price', 'market share', 'contract', 'order',
                'inflation', 'interest rate', 'regulatory', 'policy', 'infrastructure',
                'ceo', 'management', 'layoff', 'hiring', 'investment', 'funding','industry','business'
            ]  
            
            # Dynamically inject the sector and industry into the acceptable keywords
            if sector: valid_keywords.extend(sector.split())
            if industry: valid_keywords.extend(industry.split())
            
            # Additional broad net for quieter stocks
            valid_keywords.extend(['stock', 'shares', 'market', 'rating', 'target'])
                      
            if not any(word in title_lower for word in valid_keywords): continue 
                
            sentiment = analyzer.polarity_scores(title)['compound']
            scores.append(sentiment)
            
            valid_articles.append(f"• {title}")
            
            if len(scores) == 3: break 
                
        if not scores: return f"<b>System Sentiment:</b> ⚪ NEUTRAL <br><br><b>Top Filtered Headlines:</b><br>• No highly relevant financial headlines found today."
            
        avg_sentiment = sum(scores) / len(scores)
        sentiment_tag = "🟢 BULLISH" if avg_sentiment > 0.15 else "🔴 BEARISH" if avg_sentiment < -0.15 else "⚪ NEUTRAL"
            
        output = f"<b>System Sentiment:</b> {sentiment_tag} (Score: {avg_sentiment:+.2f})<br><br>"
        output += "<b>Top Filtered Headlines:</b><br>" + "<br>".join(valid_articles)
        
        return output
        
    except Exception as e:
        return f"Sentiment Engine Offline. Error: {e}"
