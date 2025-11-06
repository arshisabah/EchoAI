// ============================================
// EmotionIndicator.jsx
// ============================================
import React from 'react';
import { Heart } from 'lucide-react';

const EMOTION_CONFIG = {
  happy: { icon: '😊', color: '#10b981', name: 'Happy' },
  sad: { icon: '😔', color: '#6366f1', name: 'Sad' },
  angry: { icon: '😠', color: '#ef4444', name: 'Angry' },
  neutral: { icon: '😐', color: '#64748b', name: 'Neutral' },
  excited: { icon: '🎉', color: '#f59e0b', name: 'Excited' },
  frustrated: { icon: '😤', color: '#f97316', name: 'Frustrated' },
  confused: { icon: '🤔', color: '#8b5cf6', name: 'Confused' },
  anxious: { icon: '😰', color: '#ec4899', name: 'Anxious' },
};

const EmotionIndicator = ({ emotion, guidance }) => {
  const config = EMOTION_CONFIG[emotion] || EMOTION_CONFIG.neutral;

  return (
    <div className="emotion-panel">
      <h3>
        <Heart size={18} />
        Current Emotion
      </h3>
      <div className="emotion-display" style={{ borderLeft: `4px solid ${config.color}` }}>
        <div className="emotion-icon">{config.icon}</div>
        <div className="emotion-name" style={{ color: config.color }}>
          {config.name}
        </div>
      </div>

      {guidance && (
        <div className="emotion-guidance">
          <h4>💡 Response Guidance</h4>
          <div className="guidance-item">{guidance.primary_guidance}</div>
          {guidance.recommended_phrases && (
            <div className="guidance-section">
              <strong>Suggested Phrases:</strong>
              {guidance.recommended_phrases.slice(0, 2).map((phrase, i) => (
                <div key={i} className="guidance-item">• {phrase}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EmotionIndicator;