import React, { useState, useEffect } from 'react';
import { 
  CheckSquare, Plus, RefreshCw, Loader, User, 
  Calendar, AlertCircle, Filter, Download 
} from 'lucide-react';
import { meetingAPI } from '../../services/api';

const TaskPanel = ({ roomId, currentUser }) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // all, my-tasks, pending, completed
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadTasks();
  }, [roomId]);

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await meetingAPI.getTasks(roomId);
      setTasks(data.tasks || []);
    } catch (error) {
      console.error('Error loading tasks:', error);
      setError('Failed to load tasks');
    } finally {
      setLoading(false);
    }
  };

  const handleExtractTasks = async () => {
    setExtracting(true);
    setError(null);
    try {
      const data = await meetingAPI.extractTasks(roomId);
      setTasks(data.extracted_tasks || []);
    } catch (error) {
      console.error('Error extracting tasks:', error);
      setError('Failed to extract tasks');
      alert('Failed to extract tasks. Make sure there is transcript content available.');
    } finally {
      setExtracting(false);
    }
  };

  const getPriorityColor = (priority) => {
    const colors = {
      critical: '#ef4444',
      high: '#f97316',
      medium: '#f59e0b',
      low: '#10b981',
    };
    return colors[priority] || colors.medium;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return '✅';
      case 'in_progress':
        return '🔄';
      case 'blocked':
        return '🚫';
      default:
        return '⏳';
    }
  };

  const filteredTasks = tasks.filter(task => {
    if (filter === 'my-tasks') {
      return task.assigned_to === currentUser?.username;
    }
    if (filter === 'pending') {
      return task.status === 'pending';
    }
    if (filter === 'completed') {
      return task.status === 'completed';
    }
    return true;
  });

  const taskStats = {
    total: tasks.length,
    myTasks: tasks.filter(t => t.assigned_to === currentUser?.username).length,
    pending: tasks.filter(t => t.status === 'pending').length,
    completed: tasks.filter(t => t.status === 'completed').length,
  };

  if (loading && tasks.length === 0) {
    return (
      <div className="task-panel">
        <div className="task-loading">
          <Loader className="spinner" size={48} />
          <p>Loading tasks...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="task-panel">
      <div className="task-header">
        <div className="header-left">
          <CheckSquare size={20} />
          <h3>Tasks & Action Items</h3>
          <span className="badge">{tasks.length}</span>
        </div>
        <div className="task-actions">
          <button 
            className="btn-icon-sm" 
            onClick={loadTasks}
            disabled={loading}
            title="Refresh Tasks"
          >
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
          </button>
          <button 
            className="btn-primary btn-sm" 
            onClick={handleExtractTasks}
            disabled={extracting}
          >
            {extracting ? (
              <>
                <Loader size={16} className="spinning" />
                Extracting...
              </>
            ) : (
              <>
                <AlertCircle size={16} />
                AI Extract
              </>
            )}
          </button>
        </div>
      </div>

      {/* Task Statistics */}
      <div className="task-stats">
        <div className="task-stat-item" onClick={() => setFilter('all')}>
          <span className="stat-value">{taskStats.total}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="task-stat-item" onClick={() => setFilter('my-tasks')}>
          <span className="stat-value">{taskStats.myTasks}</span>
          <span className="stat-label">My Tasks</span>
        </div>
        <div className="task-stat-item" onClick={() => setFilter('pending')}>
          <span className="stat-value">{taskStats.pending}</span>
          <span className="stat-label">Pending</span>
        </div>
        <div className="task-stat-item" onClick={() => setFilter('completed')}>
          <span className="stat-value">{taskStats.completed}</span>
          <span className="stat-label">Done</span>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="task-filters">
        <button 
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All Tasks
        </button>
        <button 
          className={`filter-btn ${filter === 'my-tasks' ? 'active' : ''}`}
          onClick={() => setFilter('my-tasks')}
        >
          My Tasks
        </button>
        <button 
          className={`filter-btn ${filter === 'pending' ? 'active' : ''}`}
          onClick={() => setFilter('pending')}
        >
          Pending
        </button>
        <button 
          className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          Completed
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="task-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Tasks List */}
      <div className="task-list">
        {filteredTasks.length === 0 ? (
          <div className="task-empty">
            <CheckSquare size={48} />
            <p>No tasks yet</p>
            <span>
              {tasks.length === 0 
                ? 'Click "AI Extract" to automatically detect tasks from the transcript'
                : 'No tasks match your filter'}
            </span>
          </div>
        ) : (
          filteredTasks.map((task, index) => (
            <div 
              key={task.task_id || index} 
              className={`task-item ${task.status === 'completed' ? 'completed' : ''}`}
            >
              <div className="task-item-header">
                <div className="task-status-icon">
                  {getStatusIcon(task.status)}
                </div>
                <div className="task-priority-badge" style={{ 
                  backgroundColor: `${getPriorityColor(task.priority)}20`,
                  color: getPriorityColor(task.priority)
                }}>
                  {task.priority}
                </div>
              </div>

              <div className="task-item-content">
                <h4 className="task-title">{task.title}</h4>
                {task.description && (
                  <p className="task-description">{task.description}</p>
                )}
              </div>

              <div className="task-item-footer">
                <div className="task-assignee">
                  <User size={14} />
                  <span>{task.assigned_to}</span>
                </div>
                {task.due_date && (
                  <div className="task-due-date">
                    <Calendar size={14} />
                    <span>
                      {new Date(task.due_date).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              {task.context && (
                <div className="task-context">
                  <small>Context: "{task.context}"</small>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Extraction Info */}
      {tasks.length > 0 && (
        <div className="task-footer">
          <div className="extraction-info">
            <AlertCircle size={14} />
            <span>
              Tasks automatically extracted from transcript using AI
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default TaskPanel;