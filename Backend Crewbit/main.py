from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

from sentiment import sentiment_pipeline
from vectorstore import get_retriever
from hr_agent import query_hr_agent

# Initialize FastAPI app once
app = FastAPI()

# Enable CORS for React frontend (localhost on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
    "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories and constants
UPLOAD_DIR = "policy_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_LOCATION = "./chrome_langchain_db"
COLLECTION_NAME = "HrPolicy"

# Root health check endpoint
@app.get("/")
def root():
    return {"message": "HR Assistant API is running!"}


# Function to ingest PDF to vector store
def ingest_pdf_to_vector(pdf_path: str) -> int:
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(documents)

    embeddings = OllamaEmbeddings(model="mxbai-embed-large")

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=DB_LOCATION,
        embedding_function=embeddings
    )

    # Generate unique IDs for vector chunks
    ids = [str(uuid.uuid4()) for _ in chunks]

    # Add documents to vector store
    vector_store.add_documents(documents=chunks, ids=ids)
    # If your Chroma version needs explicit persistence, uncomment below:
    # vector_store.persist()

    return len(chunks)


# Upload and ingest PDF endpoint
@app.post("/upload-policy")
async def upload_policy(file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())

    chunk_count = ingest_pdf_to_vector(file_location)

    return {"filename": file.filename, "status": "uploaded and ingested", "chunks_added": chunk_count}


# Pydantic model for queries
class QueryRequest(BaseModel):
    question: str


# Query endpoint: performs retrieval, sentiment analysis & answers via LLM
@app.post("/ask-query")
async def ask_query(req: QueryRequest):
    question = req.question

    # Initialize retriever (consider caching for performance)
    retriever = get_retriever()

    # 1. Sentiment analysis on the query
    sentiment_result = sentiment_pipeline(question[:512])
    user_sentiment = sentiment_result[0]['label']

    # 2. Retrieve relevant chunks
    retrieved_docs = retriever.invoke(question)
    if hasattr(retrieved_docs, '__iter__') and not isinstance(retrieved_docs, str):
        context = "\n\n".join([doc.page_content if hasattr(doc, 'page_content') else str(doc) for doc in retrieved_docs])
    else:
        context = str(retrieved_docs)

    # 3. Query the HR assistant LLM
    answer = query_hr_agent(context, question, user_sentiment)
    return {"answer": answer}
