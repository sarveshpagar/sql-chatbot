import streamlit as st
import json
import pandas as pd
from sqlalchemy import create_engine, inspect
from together import Together
from dotenv import load_dotenv
import os
import re

# Load environment variables
load_dotenv()
together_api_key = os.getenv("TOGETHER_API_KEY")

together = Together(api_key=together_api_key)

# Custom CSS styling
st.markdown(
    """
    <style>
    .user-message {
        text-align: right;
        background-color: #D1E7DD;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
        display: inline-block;
        max-width: 70%;
        float: right;
        clear: both;
    }
    .assistant-message {
        text-align: left;
        background-color: #F8D7DA;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
        display: inline-block;
        max-width: 70%;
        float: left;
        clear: both;
    }
    .stChatInput {
        position: fixed;
        bottom: 3rem;
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Streamlit UI Setup
st.title("AI-Powered SQL Chatbot")
st.markdown("Welcome! Enter your database connection string to start a conversation with the AI-powered SQL assistant.")

# Session state initialization
if "connection_string" not in st.session_state:
    st.session_state.connection_string = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for connection string
with st.sidebar:
    st.subheader("Database Connection")
    connection_string = st.text_input(
        "Connection String", 
        st.session_state.connection_string, 
        type="password",
        help="Format: dialect+driver://username:password@host:port/database"
    )
    if st.button("Save Connection"):
        st.session_state.connection_string = connection_string
        st.success("Connection saved!")

# Determine database type
def detect_db_type(connection_string):
    if connection_string.startswith("sqlite"):
        return "sqlite"
    elif "mysql" in connection_string:
        return "mysql"
    return "unknown"

# Database schema functions
def get_db_schema(connection_string):
    try:
        engine = create_engine(connection_string)
        inspector = inspect(engine)
        schema = {}
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            schema[table_name] = [col["name"] for col in columns]
        return schema
    except Exception as e:
        return f"Error connecting to database: {str(e)}"

# AI functions
def generate_sql(natural_query, schema, db_type):
    system_prompt = f"""
    You are an expert SQL generator. Generate a valid SQL query based on the schema:
    {json.dumps(schema, indent=2)}
    
    Rules:
    - Ensure the query is syntactically correct for {db_type.upper()} databases.
    """
    
    response = together.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate SQL for: {natural_query}"}
        ]
    )
    
    sql_response = response.choices[0].message.content.strip()
    sql_query_match = re.search(r"```sql\n(.*?)\n```", sql_response, re.DOTALL)
    return sql_query_match.group(1).strip() if sql_query_match else sql_response

# Execute SQL
def execute_sql(connection_string, sql_query):
    try:
        engine = create_engine(connection_string)
        with engine.connect() as connection:
            return pd.read_sql(sql_query, connection)
    except Exception as e:
        return f"Error executing query: {str(e)}"

# Summarize results
def summarize_results(results):
    response = together.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        messages=[
            {"role": "user", "content": f"Convert this data into a human-readable response: {results.to_string()}"}
        ]
    )
    return response.choices[0].message.content.strip()

# Chat interface
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f'<div class="user-message">{message["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-message">{message["content"]}</div>', unsafe_allow_html=True)

if prompt := st.chat_input("Ask your database question..."):
    if not st.session_state.connection_string:
        st.error("Please save a valid connection string first")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        try:
            db_type = detect_db_type(st.session_state.connection_string)
            schema = get_db_schema(st.session_state.connection_string)
            sql_query = generate_sql(prompt, schema, db_type)
            results = execute_sql(st.session_state.connection_string, sql_query)
            
            if isinstance(results, pd.DataFrame):
                summary = summarize_results(results)
                st.session_state.messages.append({"role": "assistant", "content": summary})
                st.markdown(f'<div class="assistant-message">{summary}</div>', unsafe_allow_html=True)
            else:
                st.session_state.messages.append({"role": "assistant", "content": results})
                st.markdown(f'<div class="assistant-message">{results}</div>', unsafe_allow_html=True)
        
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
            st.markdown(f'<div class="assistant-message">{error_msg}</div>', unsafe_allow_html=True)


#sqlite:///D:/Sarvesh/walmart_sales_2.db