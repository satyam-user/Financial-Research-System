import yfinance as yf
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

nltk.download('vader_lexicon', quiet=True)

def run_sentiment_analysis(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        news = stock.news
        if not news: return f"No major recent news detected for {ticker_symbol}."
        
        company_name = stock.info.get('shortName', ticker_symbol).split()[0].lower()
        ticker_lower = ticker_symbol.lower()
        analyzer = SentimentIntensityAnalyzer()
        scores = []
        valid_articles = []
        
        for article in news:
            title = article.get('title', '')
            if not title and 'content' in article: title = article['content'].get('title', '')
            if not title: continue 
                
            title_lower = title.lower()
            # Expanded to cover Tech, Industrial, Consumer, and Financial sectors
            valid_keywords = [
                # Ticker & Name (Always priority)
                ticker_lower, company_name, 
                
                # Growth & Strategy
                'growth', 'expansion', 'acquisition', 'm&a', 'merger', 'strategy', 'partnership',
                
                # Financial Performance
                'earnings', 'revenue', 'profit', 'margin', 'dividend', 'guidance', 'forecast', 'ebitda',
                
                # Macro & Sector-Specific
                'demand', 'supply', 'production', 'price', 'market share', 'contract', 'order',
                'inflation', 'interest rate', 'regulatory', 'policy', 'infrastructure',
                
                # General Corporate
                'ceo', 'management', 'layoff', 'hiring', 'investment', 'funding'
            ]            
            if not any(word in title_lower for word in valid_keywords): continue 
                
            sentiment = analyzer.polarity_scores(title)['compound']
            scores.append(sentiment)
            
            # CHANGE 1: Removed the [{sentiment:+.2f}] part here
            valid_articles.append(f"• {title}")
            
            if len(scores) == 3: break 
                
        if not scores: return f"No highly relevant financial headlines found today. Defaulting to neutral market sentiment."
            
        avg_sentiment = sum(scores) / len(scores)
        sentiment_tag = "BULLISH 🟢" if avg_sentiment > 0.15 else "BEARISH 🔴" if avg_sentiment < -0.15 else "NEUTRAL ⚪"
            
        # CHANGE 2: Using <b> tags and <br> because your output goes into an HTML <div>
        output = f"<b>Sentiment:</b> {sentiment_tag} (Score: {avg_sentiment:+.2f})<br><br>"
        output += "<b>Top Filtered Headlines:</b><br>" + "<br>".join(valid_articles)
        
        return output
    except Exception as e:
        return f"NLP Engine Offline. Error: {e}"
