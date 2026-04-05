import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.documents import Document

# --- Step 3: Load the API Key ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# --- Step 4 & 6: Initialize the AI Models (lazy, only when API key is present) ---
embeddings = None
llm = None
if api_key:
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
        llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0)
    except Exception:
        pass

# --- Step 5: Storage Path ---
vector_db_path = "data/chroma_db"


def process_stock_data(ticker, data_dict):
    """
    Steps 9, 10, 11 & 12: Converting SQL/DataFrame rows into Fact Sentences.
    Includes 20-year Technical (CSV) and 4-year Fundamental (SQL) data.
    """
    all_docs = []
    
    # --- Step 9.5: Process 20-Year Technical (Price) History ---
    # --- Step 9.5: Clean and Process 20-Year Technical History ---
    df_tech = data_dict.get('df_historical_tech')
    if df_tech is not None and not df_tech.empty:
        # 1. Convert to datetime and STRIP timezones/times for clean resampling
        df_tech.index = pd.to_datetime(df_tech.index, utc=True).tz_localize(None)
        
        # 2. Resample by Year (using 'YE' for Year-End)
        # We use .mean() to ensure even if a specific day is missing, the year is caught
        # Tell Pandas to only calculate the mean for columns that are numbers
        df_yearly = df_tech.select_dtypes(include=[np.number]).resample('YE').mean()
        
        for date, row in df_yearly.iterrows():
            year = str(date.year)
            if not pd.isna(row['Close']):
                price = round(row['Close'], 2)
                text = f"In the year {year}, the average stock price for {ticker} was {price} dollars."
                
                doc = Document(
                    page_content=text, 
                    metadata={"ticker": ticker, "type": "price_history", "year": year}
                )
                all_docs.append(doc)
    # --- Step 10: Process Annual Income Statement ---
    df_isy = data_dict.get('df_isy')
    if df_isy is not None and not df_isy.empty:
        for date, row in df_isy.iterrows():
            year = str(date).split('-')[0]
            text = (f"In the fiscal year {year}, {ticker} reported a Total Revenue of "
                    f"{row['Total Revenue']} billion dollars and a Net Income of "
                    f"{row['Net Income']} billion dollars.")
            
            doc = Document(
                page_content=text,
                metadata={"ticker": ticker, "type": "annual_income", "year": year}
            )
            all_docs.append(doc)

    # --- Step 11: Updated Balance Sheet Loop ---
    df_bs = data_dict.get('df_bs')
    if df_bs is not None and not df_bs.empty:
        for date, row in df_bs.iterrows():
            year = str(date).split('-')[0]
            text = (f"As of the fiscal year {year}, {ticker} reported Total Debt of "
                    f"{row['Total Debt']} billion dollars and Stockholders Equity of "
                    f"{row['Stockholders Equity']} billion dollars.")
            
            doc = Document(
                page_content=text, 
                metadata={"ticker": ticker, "type": "balance_sheet", "year": year}
            )
            all_docs.append(doc)

    # --- Step 12: Add AI Risk & Unicorn Analysis ---
    score = data_dict.get('total_score', 'Unknown')
    risk_status = data_dict.get('risk_message', 'Stable')
    
    summary_text = (f"As of March 28, 2026, the Unicorn Finder AI assigned {ticker} "
                    f"a health score of {score} out of 10. The Risk Radar flagged "
                    f"this stock as {risk_status} based on historical volatility.")
    
    all_docs.append(Document(page_content=summary_text, metadata={"ticker": ticker, "type": "analysis_summary"}))
    
    return all_docs


# --- Step 13: The Save Function ---
def save_to_vector_db(all_docs):
    """
    Takes the fact sentences and stores them in the ChromaDB folder.
    """
    if not all_docs:
        return "No data to save."
        
    vector_db = Chroma.from_documents(
        documents=all_docs, 
        embedding=embeddings, 
        persist_directory=vector_db_path
    )
    return "✅ Knowledge Base Updated Successfully."

# --- Step 14: The Retrieval Logic ---
# --- Updated Step 14: The Retrieval Logic (Fixed for 20-year history) ---
# --- Updated Step 14: The Filtered Retrieval Logic ---
def get_chat_response(user_query, current_ticker): # Added current_ticker here
    """
    Search the database ONLY for the current stock's facts.
    """
    db = Chroma(persist_directory=vector_db_path, embedding_function=embeddings)
    
    # We tell the Librarian: "Only grab facts where the ticker is [current_ticker]"
    docs = db.similarity_search(
        user_query, 
        k=40, 
        filter={"ticker": current_ticker} 
    )
    
    context = "\n".join([doc.page_content for doc in docs])
    
    prompt = f"""
    You are a Senior Financial Analyst for {current_ticker}. 
    Use the following data to answer the user. 
    
    DATA:
    {context}
    
    USER QUESTION: {user_query}
    """
    
    response = llm.invoke(prompt)
    return response.content