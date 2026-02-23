from langchain_ollama import OllamaEmbeddings
from database import SessionLocal, PolicyVector, init_db
import json
import os
from dotenv import load_dotenv

load_dotenv()

def seed_policies():
    db = SessionLocal()
    # Use Ollama for embeddings - much lighter than local sentence-transformers
    embeddings = OllamaEmbeddings(
        model=os.getenv("MODEL_NAME", "llama3.2"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    
    policies = [
        {
            "content": "Cheque Clearing Policy: Domestic cheques usually clear within 2 business days. Individual banks may hold funds for up to 5 days for larger amounts.",
            "metadata": {"category": "Cheque Clearing"}
        },
        {
            "content": "ACH Clearing Policy: Standard ACH transfers take 1-3 business days. Same-day ACH is available for most transactions submitted before 10 AM.",
            "metadata": {"category": "ACH"}
        },
        {
            "content": "Fraud Prevention: We use AI-based monitoring. If a transaction is flagged as high-risk, we will send an email alert and hold the process until confirmed.",
            "metadata": {"category": "Security"}
        }
    ]
    
    # Simple check to avoid duplicate seeding
    if db.query(PolicyVector).count() > 0:
        print("Policies already seeded.")
        return

    for p in policies:
        # langchain-ollama returns embeddings via embed_query
        embedding = embeddings.embed_query(p["content"])
        policy = PolicyVector(
            content=p["content"],
            metadata_json=json.dumps(p["metadata"]),
            embedding=embedding
        )
        db.add(policy)
    
    db.commit()
    db.close()
    print("Policies seeded successfully via Ollama.")

if __name__ == "__main__":
    init_db()
    seed_policies()
