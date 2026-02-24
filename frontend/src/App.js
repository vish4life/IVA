import React, { useState, useRef, useEffect } from 'react';
import './oai-styles.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [user, setUser] = useState(null); // { name, email, token }
  const [view, setView] = useState('login'); // 'login', 'register', 'chat'
  const [loading, setLoading] = useState(false);
  
  // Form States
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [regNum, setRegNum] = useState('');

  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);
  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);
      
      const response = await fetch('http://localhost:8000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
      const data = await response.json();
      if (response.ok) {
        setUser({ ...data.user, token: data.access_token });
        setView('chat');
      } else {
        alert(data.detail || "Login failed");
      }
    } catch (err) {
      alert("Error connecting to server");
    }
    setLoading(false);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email,
          password,
          registration_number: regNum
        })
      });
      if (response.ok) {
        alert("Registration successful! Please login.");
        setView('login');
      } else {
        const data = await response.json();
        alert(data.detail || "Registration failed");
      }
    } catch (err) {
      alert("Error connecting to server");
    }
    setLoading(false);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      mediaRecorder.current.ondataavailable = (e) => audioChunks.current.push(e.data);
      mediaRecorder.current.onstop = sendAudio;
      audioChunks.current = [];
      mediaRecorder.current.start();
      setIsRecording(true);
    } catch (err) {
      alert("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop();
    }
    setIsRecording(false);
  };

  const sendAudio = async () => {
    const audioBlob = new Blob(audioChunks.current, { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.wav');

    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/voice', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${user.token}` },
        body: formData,
      });
      const data = await response.json();
      
      setMessages(prev => [
        ...prev, 
        { role: 'user', text: data.user_text || " (Voice input received) " },
        { role: 'ai', text: data.response_text }
      ]);

      if (data.audio_url) {
        const audio = new Audio(`http://localhost:8000${data.audio_url}`);
        audio.play().catch(e => console.error("Audio play failed"));
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'ai', text: "Voice processing failed." }]);
    }
    setLoading(false);
  };

  if (view === 'login') {
    return (
      <div className="auth-container">
        <div className="auth-box">
          <h2>Welcome Back</h2>
          <form onSubmit={handleLogin}>
            <input placeholder="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
            <input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
            <button type="submit" disabled={loading}>{loading ? 'Verifying...' : 'Log In'}</button>
          </form>
          <p onClick={() => setView('register')}>New user? Register here</p>
        </div>
      </div>
    );
  }

  if (view === 'register') {
    return (
      <div className="auth-container">
        <div className="auth-box">
          <h2>Create Account</h2>
          <form onSubmit={handleRegister}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input placeholder="First Name" value={firstName} onChange={e => setFirstName(e.target.value)} required />
              <input placeholder="Last Name" value={lastName} onChange={e => setLastName(e.target.value)} required />
            </div>
            <input placeholder="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
            <input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
            <input placeholder="Account/Card/Loan #" value={regNum} onChange={e => setRegNum(e.target.value)} required />
            <button type="submit" disabled={loading}>{loading ? 'Processing...' : 'Register'}</button>
          </form>
          <p onClick={() => setView('login')}>Already have an account? Log in</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <header>
        <h1>🤖 IVA - {user.name}</h1>
        <button className="logout-btn" onClick={() => { setUser(null); setView('login'); }}>Logout</button>
      </header>

      <main className="chat-history">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role === 'user' ? 'user-msg' : 'ai-msg'}`}>
            {msg.text}
          </div>
        ))}
        {loading && <div className="message ai-msg">Processing...</div>}
        <div ref={chatEndRef} />
      </main>

      <footer className="voice-section">
        <button 
          className={`voice-btn ${isRecording ? 'recording' : ''}`}
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onTouchStart={startRecording}
          onTouchEnd={stopRecording}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
          </svg>
        </button>
        <p>{isRecording ? 'Listening...' : 'Hold to Talk'}</p>
      </footer>
    </div>
  );
}

export default App;
