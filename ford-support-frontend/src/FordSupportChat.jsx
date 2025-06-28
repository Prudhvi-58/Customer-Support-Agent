// src/FordSupportChat.jsx

import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Car } from 'lucide-react';
import ReactMarkdown from 'react-markdown'; // <-- 1. Import the library

const FordSupportChat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const API_BASE_URL = 'http://localhost:8000';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startChatSession = async () => {
    setIsConnecting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const data = await response.json();
      setSessionId(data.session_id); 
      
      setMessages([{
        id: Date.now(),
        text: `Welcome! I'm your Ford Customer Support assistant. How can I help?`,
        sender: 'bot',
        timestamp: new Date().toLocaleTimeString()
      }]);
      
    } catch (error) {
      console.error('Failed to start chat session:', error);
      alert(`Failed to start chat session. Please ensure the backend is running. Error: ${error.message}`);
      setSessionId(null); 
    } finally {
      setIsConnecting(false);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || !sessionId) return;

    const userMessage = {
      id: Date.now(),
      text: inputMessage,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputMessage;
    setInputMessage('');
    setIsSending(true);
    
    // This placeholder will now trigger our new loader
    const botMessagePlaceholderId = Date.now() + 1;
    setMessages(prev => [
      ...prev, 
      {
        id: botMessagePlaceholderId, 
        text: '', // Start with empty text to show the loader
        sender: 'bot', 
        isStreaming: true, 
        timestamp: new Date().toLocaleTimeString() 
      }
    ]);

    try {
      const response = await fetch(`${API_BASE_URL}/session/${sessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: currentInput })
      });

      if (!response.ok) {
        const errorText = await response.text(); 
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
      }
      
      const messageBlock = buffer.trim();

      if (messageBlock.startsWith('data:')) {
        const content = messageBlock.substring(5).trim();
        
        // Update the UI with the full content and stop streaming
        setMessages(prevMsgs => prevMsgs.map(msg => 
            (msg.id === botMessagePlaceholderId) 
              ? {...msg, text: content, isStreaming: false }
              : msg
        ));

      } else if (messageBlock) { 
        console.warn('Frontend: Unprocessed, non-data content left in buffer:', `[${messageBlock}]`);
         setMessages(prevMsgs => prevMsgs.map(msg => 
            (msg.id === botMessagePlaceholderId) 
              ? {...msg, text: 'Error: Received malformed response from server.', isError: true, isStreaming: false} 
              : msg
        ));
      } else {
        // Handle cases with no response
         setMessages(prevMsgs => prevMsgs.map(msg => 
            (msg.id === botMessagePlaceholderId) 
              ? {...msg, text: 'No response from server.', isError: true, isStreaming: false} 
              : msg
        ));
      }

    } catch (error) {
      console.error('Frontend: Chat error:', error);
      setMessages(prev => {
        const newMessages = prev.filter(msg => !(msg.id === botMessagePlaceholderId));
        return [...newMessages, {
          id: Date.now() + 2, 
          text: `Something went wrong: ${error.message}. Please try again.`,
          sender: 'bot',
          isError: true,
          timestamp: new Date().toLocaleTimeString()
        }];
      });
    } finally {
      setIsSending(false);
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleChatKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputMessage.trim() && !isSending) {
        sendMessage();
      }
    }
  };

  return (
    <div className="chat-container">
      {!sessionId ? (
        <div className="card">
          <div className="logo-header">
            <Car className="icon" />
            <h1>Ford Support</h1>
          </div>
          <button onClick={startChatSession} disabled={isConnecting}>
            {isConnecting ? <Loader2 className="loader animate-spin" /> : 'Connect to Assistant'}
          </button>
        </div>
      ) : (
        <div className="chat-box">
          <div className="chat-header">
            <Car className="icon" />
            <div className="header-info">
              <span className="status-text">Connected to Ford Support</span>
            </div>
          </div>

          <div className="chat-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.sender} ${msg.isError ? 'error' : ''}`}>
                <div className="message-content">
                  {/*
                    2. ADDED LOADER AND MARKDOWN LOGIC
                  */}
                  <div className="message-text">
                    {/* If streaming and text is empty, show the "thinking" loader */}
                    {msg.isStreaming && !msg.text && (
                      <div className="loading-indicator">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Ford Assistant is thinking...</span>
                      </div>
                    )}

                    {/* Render the message text using ReactMarkdown */}
                    <ReactMarkdown children={msg.text} />

                    {/* Show blinking cursor only if we are actively receiving text */}
                    {msg.isStreaming && msg.text && <span className="blinking-cursor">|</span>}
                  </div>
                  
                  {/* Only show timestamp if message is complete and has text */}
                  {!msg.isStreaming && msg.text && <div className="message-time">{msg.timestamp}</div>}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleChatKeyDown}
              placeholder="Type your message..."
              rows="2"
              disabled={isSending}
            />
            <button 
              onClick={sendMessage} 
              disabled={!inputMessage.trim() || isSending}
              className={isSending ? 'loading' : ''}
            >
              {isSending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default FordSupportChat;