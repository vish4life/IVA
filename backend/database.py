import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector
import datetime
from dotenv import load_dotenv

load_dotenv()

# Use the sync-friendly URL (remove +asyncpg if present automatically as a safeguard)
raw_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/banking_db")
DATABASE_URL = raw_url.replace("+asyncpg", "")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    registration_number = Column(String, unique=True)
    phone = Column(String)
    address = Column(String)
    is_authenticated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    account_number = Column(String, unique=True, index=True)
    account_type = Column(String) # Savings, Checking
    balance = Column(Float, default=0.0)

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    type = Column(String) # Loan, Credit Card, Insurance, Account Opening
    status = Column(String, default="Pending") # Pending, Approved, Rejected
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float)
    transaction_type = Column(String) # Debit, Credit
    description = Column(String)
    is_fraudulent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PolicyVector(Base):
    __tablename__ = "policy_vectors"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    metadata_json = Column(Text)
    embedding = Column(Vector(3072)) # Matching llama3.2 embedding dimension

def init_db():
    # Only drop the vector table if there is a dimension change issue
    # For buildathon simplicity, we can drop and recreate all or just the problematic one
    print("Dropping existing tables to ensure schema matches...")
    Base.metadata.drop_all(bind=engine)
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")

if __name__ == "__main__":
    init_db()
