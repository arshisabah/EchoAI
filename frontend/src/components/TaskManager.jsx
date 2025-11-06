// ============================================
// TaskManager.jsx
// ============================================
import React, { useState, useEffect } from 'react';
import { CheckSquare, Plus, RefreshCw } from 'lucide-react';
import { meetingAPI } from '../services/api';

const TaskManager = ({ roomId }) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadTasks();
  }, [roomId]);

  const loadTasks = async () => {
    try {
      const data = await meetingAPI.getTasks(roomId);
      setTasks(data.tasks || []);
    } catch (error) {
      console.error('Error loading tasks:', error);
    }
  };

  const handleExtractTasks = async () => {
    setLoading(true);
    try {
      const data = await meetingAPI.extractTasks(roomId);
      setTasks(data.extracted_tasks || []);
    } catch (error) {
      console.error('Error extracting tasks:', error);
      alert('Failed to extract tasks');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="task-manager">
      <div className="task-header">
        <h3>
          <CheckSquare size={18} />
          Tasks
        </h3>
        <button
          className="btn-primary btn-sm"
          onClick={handleExtractTasks}
          disabled={loading}
        >
          <RefreshCw size={16} />
          {loading ? 'Extracting...' : 'Extract Tasks'}
        </button>
      </div>

      {tasks.length === 0 ? (
        <div className="empty-state">
          <p>No tasks yet. Click "Extract Tasks" to analyze the transcript.</p>
        </div>
      ) : (
        <div className="tasks-list">
          {tasks.map((task, index) => (
            <div key={task.task_id || index} className="task-item">
              <div className="task-title">{task.title}</div>
              <div className="task-meta">
                <span>Assigned: {task.assigned_to}</span>
                <span className={`priority-${task.priority}`}>{task.priority}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TaskManager;