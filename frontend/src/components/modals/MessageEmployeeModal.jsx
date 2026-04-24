import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMessages, sendMessageToEmployee } from '../../services/api';
import Modal from './Modal';
import './MessageEmployeeModal.css';

function MessageEmployeeModal({ isOpen, onClose, employeeId, employeeName }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const queryClient = useQueryClient();

  // Reset input when modal opens/closes or employee changes
  useEffect(() => {
    if (!isOpen) setInput('');
  }, [isOpen, employeeId]);

  const { data, isLoading } = useQuery({
    queryKey: ['messages', employeeId],
    queryFn: async () => {
      const r = await getMessages(employeeId);
      // Messages are marked as read server-side on fetch — invalidate unread counts
      queryClient.invalidateQueries({ queryKey: ['unread-message-counts'] });
      return r.data;
    },
    enabled: isOpen && !!employeeId,
    refetchInterval: isOpen ? 8000 : false,
  });

  const sendMutation = useMutation({
    mutationFn: (content) => sendMessageToEmployee(employeeId, content),
    // Optimistic update — message appears instantly before server confirms
    onMutate: async (content) => {
      await queryClient.cancelQueries({ queryKey: ['messages', employeeId] });
      const previous = queryClient.getQueryData(['messages', employeeId]);
      const optimisticMsg = {
        id: `temp-${Date.now()}`,
        sender_type: 'owner',
        content,
        created_at: new Date().toISOString(),
        read: false,
        _optimistic: true,
      };
      queryClient.setQueryData(['messages', employeeId], (old) => ({
        ...old,
        messages: [...(old?.messages || []), optimisticMsg],
      }));
      setInput('');
      return { previous };
    },
    onError: (error, _content, context) => {
      // Roll back on failure
      if (context?.previous) {
        queryClient.setQueryData(['messages', employeeId], context.previous);
      }
      console.error('Failed to send message:', error);
    },
    onSettled: () => {
      // Refetch to get the real server data
      queryClient.invalidateQueries({ queryKey: ['messages', employeeId] });
      queryClient.invalidateQueries({ queryKey: ['unread-message-counts'] });
    },
  });

  const messages = data?.messages || [];

  // Auto-scroll to bottom on initial load and when new messages arrive
  const prevMsgCountRef = useRef(0);
  useEffect(() => {
    const count = messages.length;
    if (messagesEndRef.current && count !== prevMsgCountRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: count > prevMsgCountRef.current ? 'smooth' : 'auto' });
    }
    prevMsgCountRef.current = count;
  }, [messages.length]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || sendMutation.isPending) return;
    sendMutation.mutate(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
           d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  // Group messages by date
  const groupedMessages = [];
  let lastDate = '';
  messages.forEach(msg => {
    const msgDate = new Date(msg.created_at).toLocaleDateString('en-US', { 
      weekday: 'long', month: 'short', day: 'numeric' 
    });
    if (msgDate !== lastDate) {
      groupedMessages.push({ type: 'date', date: msgDate });
      lastDate = msgDate;
    }
    groupedMessages.push({ type: 'message', ...msg });
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Message ${employeeName || 'Employee'}`} size="large">
      <div className="msg-modal">
        <div className="msg-messages">
          {isLoading ? (
            <div className="msg-loading">
              <div className="loading-spinner"></div>
              <p>Loading messages...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="msg-empty">
              <div className="msg-empty-icon">
                <i className="fas fa-comments"></i>
              </div>
              <h3>Start a conversation</h3>
              <p>Send a message to {employeeName || 'this employee'}</p>
            </div>
          ) : (
            groupedMessages.map((item, i) => {
              if (item.type === 'date') {
                return (
                  <div key={`date-${i}`} className="msg-date-divider">
                    <span>{item.date}</span>
                  </div>
                );
              }
              const isOwner = item.sender_type === 'owner';
              return (
                <div key={item.id} className={`msg-bubble ${isOwner ? 'sent' : 'received'}`}>
                  <div className="msg-bubble-content">
                    <p>{item.content}</p>
                    <span className="msg-time">
                      {formatTime(item.created_at)}
                      {isOwner && item.read && <i className="fas fa-check-double msg-read-icon" title="Read"></i>}
                    </span>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="msg-input-bar">
          <textarea
            className="msg-input"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows="1"
            maxLength={2000}
          />
          <button
            className="msg-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || sendMutation.isPending}
            aria-label="Send message"
          >
            <i className={`fas ${sendMutation.isPending ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i>
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default MessageEmployeeModal;
