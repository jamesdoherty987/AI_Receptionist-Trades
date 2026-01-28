import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { sendChatMessage } from '../../services/api';
import './ChatTab.css';

function ChatTab() {
  const [conversation, setConversation] = useState([]);
  const [input, setInput] = useState('');

  const chatMutation = useMutation({
    mutationFn: ({ message, conversation }) => sendChatMessage(message, conversation),
    onSuccess: (response) => {
      const aiResponse = response.data.response;
      setConversation(prev => [
        ...prev,
        { role: 'assistant', content: aiResponse }
      ]);
    },
    onError: (error) => {
      console.error('Chat error:', error);
      setConversation(prev => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }
      ]);
    },
  });

  const handleSendMessage = () => {
    if (!input.trim() || chatMutation.isPending) return;

    const userMessage = input.trim();
    setInput('');

    // Add user message to conversation
    const newConversation = [
      ...conversation,
      { role: 'user', content: userMessage }
    ];
    setConversation(newConversation);

    // Send to API
    chatMutation.mutate({ message: userMessage, conversation: newConversation });
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="chat-tab">
      <div className="chat-header">
        <h2>AI Assistant Chat</h2>
        <p className="chat-subtitle">Ask questions about your business, appointments, and customers</p>
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {conversation.length === 0 ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">
                <i className="fas fa-robot"></i>
              </div>
              <h3>Start a conversation</h3>
              <p>Ask me anything about your business operations</p>
              <div className="chat-suggestions">
                <button onClick={() => setInput('How many appointments do I have this week?')}>
                  📅 This week's appointments
                </button>
                <button onClick={() => setInput('Who are my top customers?')}>
                  👥 Top customers
                </button>
                <button onClick={() => setInput('What is my revenue this month?')}>
                  💰 Monthly revenue
                </button>
              </div>
            </div>
          ) : (
            conversation.map((message, index) => (
              <div key={index} className={`chat-message ${message.role}`}>
                <div className="message-avatar">
                  {message.role === 'user' ? (
                    <i className="fas fa-user"></i>
                  ) : (
                    <i className="fas fa-robot"></i>
                  )}
                </div>
                <div className="message-content">
                  {message.content}
                </div>
              </div>
            ))
          )}
          {chatMutation.isPending && (
            <div className="chat-message assistant">
              <div className="message-avatar">
                <i className="fas fa-robot"></i>
              </div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="chat-input-container">
          <textarea
            className="chat-input"
            placeholder="Type your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            rows="1"
          />
          <button
            className="chat-send-btn"
            onClick={handleSendMessage}
            disabled={!input.trim() || chatMutation.isPending}
          >
            <i className="fas fa-paper-plane"></i>
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatTab;
