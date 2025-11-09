import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const ChatPanel = ({ messages, onSendMessage, currentUser }) => {
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputMessage.trim()) {
      onSendMessage(inputMessage.trim());
      setInputMessage('');
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <MessageSquare size={20} />
        <h3>Chat</h3>
        <span className="badge">{messages.length}</span>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <MessageSquare size={48} />
            <p>No messages yet</p>
            <span>Start the conversation!</span>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isOwnMessage = msg.from_user === currentUser?.username;
            return (
              <div
                key={index}
                className={`chat-message ${isOwnMessage ? 'own' : 'other'}`}
              >
                {!isOwnMessage && (
                  <div className="message-avatar">
                    {msg.from_user.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="message-content">
                  {!isOwnMessage && (
                    <span className="message-sender">{msg.from_user}</span>
                  )}
                  <div className="message-text">{msg.message}</div>
                  <span className="message-time">
                    {formatDistanceToNow(new Date(msg.timestamp), { addSuffix: true })}
                  </span>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="chat-input-form">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder="Type a message..."
          className="chat-input"
        />
        <button
          type="submit"
          className="btn-icon btn-send"
          disabled={!inputMessage.trim()}
        >
          <Send size={20} />
        </button>
      </form>
    </div>
  );
};

export default ChatPanel;