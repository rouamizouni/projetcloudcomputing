import os
from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient

from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI()


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def health_check():
    return {"status": "SmartStudy API is running"}


@app.post("/ask")
def ask(request: QuestionRequest):
    client = MongoClient(os.environ.get("MONGO_URI"))
    collection = client["smartstudy"]["context"]

    embeddings = VertexAIEmbeddings(
        model_name="text-embedding-005",
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("LOCATION", "europe-west1"),
    )

    vector_store = MongoDBAtlasVectorSearch(
        collection=collection,
        embedding=embeddings,
        index_name="vector_index",
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3},
    )

    llm = ChatVertexAI(
        model_name="gemini-2.5-flash",
        temperature=0,
        max_output_tokens=1024,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("LOCATION", "europe-west1"),
    )

    system_prompt = """
You are an assistant that answers only using the provided context.
If the answer is not in the context, say that you do not know.
Do not use general knowledge.

Context:
{context}
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )

    qa_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, qa_chain)

    response = rag_chain.invoke({"input": request.question})

    return {
        "question": request.question,
        "answer": response["answer"]
    }
