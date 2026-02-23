from fastmcp import FastMCP
from sqlalchemy.orm import Session
from database import SessionLocal, Customer, Account, Transaction, Application, PolicyVector
import uuid
from typing import Dict, List, Optional
import json
import os
from langchain_ollama import OllamaEmbeddings

mcp = FastMCP("BankingService")

@mcp.tool()
def get_customer_profile(email: str) -> Dict:
    """Retrieves customer profile by email."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.email == email).first()
        if customer:
            return {
                "id": customer.id,
                "name": customer.full_name,
                "address": customer.address,
                "is_authenticated": customer.is_authenticated
            }
        return {"error": "Customer not found"}
    finally:
        db.close()

@mcp.tool()
def get_account_balance(customer_id: Optional[int] = None, email: Optional[str] = None) -> List[Dict]:
    """Checks balances for all accounts owned by a customer using ID or email."""
    db = SessionLocal()
    try:
        if email:
            customer = db.query(Customer).filter(Customer.email == email).first()
            if customer:
                customer_id = customer.id
            else:
                return [{"error": "Customer email not found"}]
        
        if not customer_id:
            return [{"error": "No ID or email provided"}]
            
        accounts = db.query(Account).filter(Account.customer_id == customer_id).all()
        return [{"account_number": acc.account_number, "type": acc.account_type, "balance": acc.balance} for acc in accounts]
    finally:
        db.close()

@mcp.tool()
def transfer_funds(from_account: str, to_account: str, amount: float, description: str = "Transfer") -> str:
    """Transfers funds between accounts and records transactions."""
    db = SessionLocal()
    try:
        sender = db.query(Account).filter(Account.account_number == from_account).first()
        receiver = db.query(Account).filter(Account.account_number == to_account).first()
        
        if not sender or not receiver:
            return "Error: One or both accounts not found."
        
        if sender.balance < amount:
            return "Error: Insufficient funds."
        
        sender.balance -= amount
        receiver.balance += amount
        
        # Record transactions
        db.add(Transaction(account_id=sender.id, amount=-amount, transaction_type="Debit", description=description))
        db.add(Transaction(account_id=receiver.id, amount=amount, transaction_type="Credit", description=description))
        
        db.commit()
        return f"Successfully transferred ${amount} from {from_account} to {to_account}."
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def apply_for_product(product_type: str, details: Optional[Dict] = None, customer_id: Optional[int] = None, email: Optional[str] = None) -> str:
    """
    Submits an application for account opening, loan, credit card, or insurance.
    
    Args:
        product_type: One of 'Account Opening', 'Loan', 'Credit Card', 'Insurance'.
        details: A dictionary containing specific application details (e.g., {"loan_amount": 5000, "reason": "Home repair"}).
        customer_id: The ID of the customer if already known/existing.
        email: The email address of the customer (required if customer_id is not provided).
    """
    if details is None:
        details = {}
    db = SessionLocal()
    try:
        # If customer_id is missing, try to find or create a placeholder for the application
        if not customer_id:
            if not email:
                return "Error: Either customer_id or email must be provided for an application."
            
            customer = db.query(Customer).filter(Customer.email == email).first()
            if customer:
                customer_id = customer.id
            else:
                # Create a minimal customer entry for the application if name is in details
                full_name = details.get("full_name", "Unknown Applicant")
                new_customer = Customer(full_name=full_name, email=email)
                db.add(new_customer)
                db.flush() # Get the ID
                customer_id = new_customer.id
        
        application = Application(
            customer_id=customer_id,
            type=product_type,
            details=json.dumps(details)
        )
        db.add(application)
        db.commit()
        return f"Application for {product_type} submitted successfully. Status: Pending. Reference ID: {application.id or 'N/A'}"
    except Exception as e:
        db.rollback()
        return f"Error submitting application: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def update_customer_address(customer_id: int, new_address: str) -> str:
    """Updates the customer's physical address."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if customer:
            customer.address = new_address
            db.commit()
            return "Address updated successfully."
        return "Error: Customer not found."
    finally:
        db.close()

@mcp.tool()
def validate_transaction_fraud(account_id: int, amount: float) -> Dict:
    """Checks if a transaction is potentially fraudulent and triggers alerts."""
    # Mock logic for buildathon: transactions > 5000 are "flagged"
    if amount > 5000:
        return {
            "status": "Flagged",
            "reason": "High value transaction",
            "action_required": "Email confirmation sent to customer as per policy."
        }
    return {"status": "Clean", "reason": "Normal transaction pattern"}

@mcp.tool()
def query_policy_rag(search_query: str) -> str:
    """
    Search the bank's policy documentation (ACH, Cheque clearing, etc.) for answers.
    Use this for questions about how things work or bank rules.
    
    Args:
        search_query: The plain text question or topic to search for in the bank's internal policies.
    """
    # LLM Resilience: Handle cases where the model sends a dictionary instead of a string
    if isinstance(search_query, dict):
        search_query = search_query.get("search_query") or search_query.get("value") or json.dumps(search_query)
    
    if not search_query:
        return "Please provide a specific query about bank policies."
    
    db = SessionLocal()
    try:
        # Use the same Ollama embeddings as used in seed_rag.py
        embeddings = OllamaEmbeddings(
            model=os.getenv("MODEL_NAME", "llama3.2"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        
        # 1. Embed the query
        query_vector = embeddings.embed_query(str(search_query))
        
        # 2. Search database
        results = db.query(PolicyVector).order_by(PolicyVector.embedding.l2_distance(query_vector)).limit(3).all()
        
        if not results:
            return "No specific policy found matching that query."
            
        context = "\n---\n".join([r.content for r in results])
        return f"Policy Results:\n{context}"
    finally:
        db.close()

if __name__ == "__main__":
    mcp.run()
