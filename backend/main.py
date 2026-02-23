import os

# Workaround for OpenMP error on Mac (Abort trap: 6)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import shutil
import os
import uuid
from faster_whisper import WhisperModel
import edge_tts
import asyncio
from agents import process_query
from database import SessionLocal, Customer, Account, Transaction
from pydantic import BaseModel, EmailStr
from typing import Optional, List

# Security Config
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="AI Banking Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth Utilities
def verify_password(plain_password, hashed_password):
    # bcrypt limit is 72 bytes. Passlib handles this, but some backends error out.
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password[:72])

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = SessionLocal()
    user = db.query(Customer).filter(Customer.email == email).first()
    db.close()
    if user is None:
        raise credentials_exception
    return user

# Models
class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    registration_number: str # Account/Card/Loan number

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatRequest(BaseModel):
    message: str

# Endpoints
@app.post("/register")
async def register(req: RegisterRequest):
    db = SessionLocal()
    if db.query(Customer).filter(Customer.email == req.email).first():
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = Customer(
        first_name=req.first_name,
        last_name=req.last_name,
        full_name=f"{req.first_name} {req.last_name}",
        email=req.email,
        hashed_password=get_password_hash(req.password),
        registration_number=req.registration_number,
        is_authenticated=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    
    # Mock Email Notification
    print(f"MOCK EMAIL SENT TO {req.email}: Welcome {req.first_name}! Your registration is successful.")
    
    return {"message": "User registered successfully"}

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    user = db.query(Customer).filter(Customer.email == form_data.username).first()
    db.close()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer", "user": {"name": user.full_name, "email": user.email}}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: Customer = Depends(get_current_user)):
    customer_info = {"id": current_user.id, "name": current_user.full_name, "email": current_user.email}
    response_text = await process_query(request.message, customer_info, True)
    return {"response": response_text}

@app.post("/voice")
async def voice_endpoint(file: UploadFile = File(...), current_user: Customer = Depends(get_current_user)):
    # 1. Save uploaded file
    file_id = str(uuid.uuid4())
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}_in.wav")
    
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file received")
            
        print(f"DEBUG: Received audio file {file.filename}, size: {len(content)} bytes")
        
        with open(input_path, "wb") as buffer:
            buffer.write(content)
        
        # 2. Transcribe (STT)
        segments, info = stt_model.transcribe(input_path, beam_size=5)
        user_text = " ".join([segment.text for segment in segments])
        
        if not user_text.strip():
            user_text = "[No speech detected]"
        
        # 3. Process with Agents
        customer_info = {"id": current_user.id, "name": current_user.full_name, "email": current_user.email}
        response_text = await process_query(user_text, customer_info, True)
        
        # 4. Generate Voice Response (TTS)
        output_path = os.path.join(UPLOAD_DIR, f"{file_id}_out.mp3")
        communicate = edge_tts.Communicate(response_text, "en-US-AvaNeural")
        await communicate.save(output_path)
        
        return {
            "user_text": user_text,
            "response_text": response_text,
            "audio_url": f"/audio/{file_id}_out.mp3"
        }
    except Exception as e:
        print(f"ERROR in voice_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup input file to save space
        if os.path.exists(input_path):
            try:
                os.remove(input_path)
            except:
                pass

# Initialization for models
model_size = "base"
stt_model = WhisperModel(model_size, device="cpu", compute_type="int8")
UPLOAD_DIR = "temp_audio"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    return FileResponse(os.path.join(UPLOAD_DIR, filename))

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
