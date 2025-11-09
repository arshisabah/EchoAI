import React from 'react';
import { Heart, TrendingUp, AlertCircle } from 'lucide-react';

const EMOTION_CONFIG = {
  happy: { icon: '😊', color: '#10b981', label: 'Happy' },
  sad: { icon: '😔', color: '#6366f1', label: 'Sad' },
  angry: { icon: '😠', color: '#ef4444', label: 'Angry' },
  neutral: { icon: '😐', color: '#64748b', label: 'Neutral' },
  excited: { icon: '🎉', color: '#f59e0b', label: 'Excited' },
  frustrated: { icon: '😤', color: '#f97316', label: 'Frustrated' },
  confused: { icon: '🤔', color: '#8b5cf6', label: 'Confused' },
  anxious: { icon: '😰', color: '#ec4899', label: 'Anxious' },
};

const EmotionPanel = ({ currentEmotion, emotionGuidance, emotionHistory }) => {
  const config = EMOTION_CONFIG[currentEmotion] || EMOTION_CONFIG.neutral;

  return (
    <div className="emotion-panel">
      <div className="emotion-panel-header">
        <Heart size={20} />
        <h3>Emotion Analysis</h3>
      </div>

      {/* Current Emotion Display */}
      <div 
        className="current-emotion-display"
        style={{ borderLeft: `4px solid ${config.color}` }}
      >
        <div className="emotion-icon-large">{config.icon}</div>
        <div className="emotion-details">
          <h4 style={{ color: config.color }}>{config.label}</h4>
          <p className="emotion-description">Current detected emotion</p>
        </div>
      </div>

      {/* Response Guidance */}
      {emotionGuidance && (
        <div className="guidance-section">
          <div className="guidance-header">
            <TrendingUp size={18} />
            <h4>Response Guidance</h4>
          </div>
          
          <div className="guidance-content">
            <div className="guidance-primary">
              <AlertCircle size={16} />
              <p>{emotionGuidance.primary_guidance}</p>
            </div>

            {emotionGuidance.recommended_phrases && emotionGuidance.recommended_phrases.length > 0 && (
              <div className="guidance-phrases">
                <h5>💡 Suggested Phrases:</h5>
                <ul>
                  {emotionGuidance.recommended_phrases.slice(0, 3).map((phrase, i) => (
                    <li key={i}>{phrase}</li>
                  ))}
                </ul>
              </div>
            )}

            {emotionGuidance.response_strategies && emotionGuidance.response_strategies.length > 0 && (
              <div className="guidance-strategies">
                <h5>✅ Key Strategies:</h5>
                <ul>
                  {emotionGuidance.response_strategies.slice(0, 3).map((strategy, i) => (
                    <li key={i}>{strategy}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Emotion History */}
      {emotionHistory && emotionHistory.length > 0 && (
        <div className="emotion-history">
          <h5>Recent Emotions</h5>
          <div className="emotion-timeline">
            {emotionHistory.slice(-5).reverse().map((emotion, i) => {
              const emotionConfig = EMOTION_CONFIG[emotion] || EMOTION_CONFIG.neutral;
              return (
                <div key={i} className="emotion-history-item">
                  <span className="emotion-icon-small">{emotionConfig.icon}</span>
                  <span style={{ color: emotionConfig.color }}>{emotionConfig.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default EmotionPanel;