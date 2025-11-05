# app/services/task_assignment.py
"""
AI-powered task extraction and assignment system.
Automatically detects action items and assigns them to team members.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    """Task status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents an action item/task."""
    task_id: str
    title: str
    description: str
    assigned_to: str
    assigned_by: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    meeting_id: str = None
    context: str = None  # Original text where task was mentioned
    dependencies: List[str] = None
    tags: List[str] = None
    
    def to_dict(self):
        """Convert to dictionary."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['due_date'] = self.due_date.isoformat() if self.due_date else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data


class TaskAssignmentEngine:
    """
    AI-powered task extraction and assignment system.
    Uses GPT to intelligently extract tasks from conversations and assign them.
    """
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}  # task_id -> Task
        self.meeting_tasks: Dict[str, List[str]] = {}  # meeting_id -> [task_ids]
        self.user_tasks: Dict[str, List[str]] = {}  # user_id -> [task_ids]
        self._client = None
        self.task_counter = 0
        logger.info("TaskAssignmentEngine initialized")
    
    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            from app.core.config import settings
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client
    
    async def extract_tasks_from_transcript(
        self,
        transcript_entries: List[Dict[str, Any]],
        meeting_id: str,
        participants: List[Dict[str, Any]]
    ) -> List[Task]:
        """
        Extract action items and tasks from meeting transcript.
        
        Args:
            transcript_entries: List of transcript entries
            meeting_id: Meeting ID
            participants: List of meeting participants
            
        Returns:
            List of extracted tasks
        """
        if not transcript_entries:
            return []
        
        try:
            # Build transcript text
            transcript_text = self._build_transcript_text(transcript_entries)
            
            # Get participant names for context
            participant_names = [p.get("username", p.get("user_id")) for p in participants]
            
            # Extract tasks using AI
            extracted_tasks = await self._ai_extract_tasks(
                transcript_text,
                meeting_id,
                participant_names
            )
            
            # Store tasks
            for task in extracted_tasks:
                self.tasks[task.task_id] = task
                
                # Index by meeting
                if meeting_id not in self.meeting_tasks:
                    self.meeting_tasks[meeting_id] = []
                self.meeting_tasks[meeting_id].append(task.task_id)
                
                # Index by user
                if task.assigned_to not in self.user_tasks:
                    self.user_tasks[task.assigned_to] = []
                self.user_tasks[task.assigned_to].append(task.task_id)
            
            logger.info(f"Extracted {len(extracted_tasks)} tasks from meeting {meeting_id}")
            return extracted_tasks
            
        except Exception as e:
            logger.error(f"Task extraction failed: {e}")
            return []
    
    def _build_transcript_text(self, entries: List[Dict[str, Any]]) -> str:
        """Build formatted transcript text."""
        lines = []
        for entry in entries:
            speaker = entry.get("speaker", "Unknown")
            text = entry.get("text", "")
            lines.append(f"{speaker}: {text}")
        return "\n".join(lines)
    
    async def _ai_extract_tasks(
        self,
        transcript_text: str,
        meeting_id: str,
        participant_names: List[str]
    ) -> List[Task]:
        """Use AI to extract tasks from transcript."""
        client = self._get_client()
        
        participants_str = ", ".join(participant_names)
        
        prompt = f"""
Analyze this meeting transcript and extract ALL action items, tasks, and commitments.

Participants: {participants_str}

For EACH task, identify:
1. What needs to be done (title and description)
2. Who should do it (must be one of the participants above, or "Unassigned")
3. Priority (critical/high/medium/low)
4. Deadline if mentioned (or estimate based on context)

Transcript:
{transcript_text}

Respond with ONLY valid JSON array:
[
  {{
    "title": "Brief task title",
    "description": "Detailed description",
    "assigned_to": "participant name or Unassigned",
    "priority": "high/medium/low",
    "due_date_days": 7,
    "context": "original text where task was mentioned"
  }}
]

IMPORTANT: 
- Return EMPTY array [] if no tasks found
- Only assign to people mentioned in participants list
- Be specific about what needs to be done
"""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting action items from meetings. Always respond with valid JSON array."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            task_data_list = json.loads(content)
            
            if not isinstance(task_data_list, list):
                task_data_list = [task_data_list]
            
            # Create Task objects
            tasks = []
            for task_data in task_data_list:
                self.task_counter += 1
                
                due_date = None
                if task_data.get("due_date_days"):
                    due_date = datetime.utcnow() + timedelta(days=int(task_data["due_date_days"]))
                
                task = Task(
                    task_id=f"task_{meeting_id}_{self.task_counter}",
                    title=task_data.get("title", "Untitled Task"),
                    description=task_data.get("description", ""),
                    assigned_to=task_data.get("assigned_to", "Unassigned"),
                    assigned_by="system",  # AI-assigned
                    priority=TaskPriority(task_data.get("priority", "medium").lower()),
                    status=TaskStatus.PENDING,
                    created_at=datetime.utcnow(),
                    due_date=due_date,
                    meeting_id=meeting_id,
                    context=task_data.get("context", ""),
                    tags=["ai-extracted"]
                )
                
                tasks.append(task)
            
            return tasks
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return []
        except Exception as e:
            logger.error(f"AI task extraction error: {e}")
            return []
    
    async def create_manual_task(
        self,
        title: str,
        description: str,
        assigned_to: str,
        assigned_by: str,
        meeting_id: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None
    ) -> Task:
        """Manually create a task."""
        self.task_counter += 1
        
        task = Task(
            task_id=f"task_manual_{self.task_counter}",
            title=title,
            description=description,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            due_date=due_date,
            meeting_id=meeting_id,
            tags=["manual"]
        )
        
        self.tasks[task.task_id] = task
        
        # Index
        if meeting_id not in self.meeting_tasks:
            self.meeting_tasks[meeting_id] = []
        self.meeting_tasks[meeting_id].append(task.task_id)
        
        if assigned_to not in self.user_tasks:
            self.user_tasks[assigned_to] = []
        self.user_tasks[assigned_to].append(task.task_id)
        
        logger.info(f"Created manual task: {task.task_id}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_meeting_tasks(self, meeting_id: str) -> List[Task]:
        """Get all tasks for a meeting."""
        task_ids = self.meeting_tasks.get(meeting_id, [])
        return [self.tasks[tid] for tid in task_ids if tid in self.tasks]
    
    def get_user_tasks(self, user_id: str) -> List[Task]:
        """Get all tasks assigned to a user."""
        task_ids = self.user_tasks.get(user_id, [])
        return [self.tasks[tid] for tid in task_ids if tid in self.tasks]
    
    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        updated_by: str
    ) -> Optional[Task]:
        """Update task status."""
        task = self.tasks.get(task_id)
        
        if not task:
            return None
        
        task.status = status
        
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
        
        logger.info(f"Task {task_id} status updated to {status.value} by {updated_by}")
        return task
    
    async def reassign_task(
        self,
        task_id: str,
        new_assignee: str,
        reassigned_by: str
    ) -> Optional[Task]:
        """Reassign a task to a different person."""
        task = self.tasks.get(task_id)
        
        if not task:
            return None
        
        old_assignee = task.assigned_to
        
        # Update task
        task.assigned_to = new_assignee
        task.assigned_by = reassigned_by
        
        # Update indices
        if old_assignee in self.user_tasks:
            self.user_tasks[old_assignee].remove(task_id)
        
        if new_assignee not in self.user_tasks:
            self.user_tasks[new_assignee] = []
        self.user_tasks[new_assignee].append(task_id)
        
        logger.info(f"Task {task_id} reassigned from {old_assignee} to {new_assignee}")
        return task
    
    def get_task_summary(self, meeting_id: str) -> Dict[str, Any]:
        """Get task summary for a meeting."""
        tasks = self.get_meeting_tasks(meeting_id)
        
        if not tasks:
            return {
                "total_tasks": 0,
                "by_status": {},
                "by_priority": {},
                "by_assignee": {}
            }
        
        # Count by status
        by_status = {}
        for status in TaskStatus:
            by_status[status.value] = len([t for t in tasks if t.status == status])
        
        # Count by priority
        by_priority = {}
        for priority in TaskPriority:
            by_priority[priority.value] = len([t for t in tasks if t.priority == priority])
        
        # Count by assignee
        by_assignee = {}
        for task in tasks:
            assignee = task.assigned_to
            if assignee not in by_assignee:
                by_assignee[assignee] = {
                    "total": 0,
                    "pending": 0,
                    "completed": 0
                }
            by_assignee[assignee]["total"] += 1
            if task.status == TaskStatus.PENDING:
                by_assignee[assignee]["pending"] += 1
            elif task.status == TaskStatus.COMPLETED:
                by_assignee[assignee]["completed"] += 1
        
        # Overdue tasks
        overdue_tasks = [
            t for t in tasks 
            if t.due_date and t.due_date < datetime.utcnow() and t.status != TaskStatus.COMPLETED
        ]
        
        return {
            "total_tasks": len(tasks),
            "by_status": by_status,
            "by_priority": by_priority,
            "by_assignee": by_assignee,
            "overdue_count": len(overdue_tasks),
            "completion_rate": (by_status.get("completed", 0) / len(tasks) * 100) if tasks else 0
        }


# Singleton
_task_assignment_engine: Optional[TaskAssignmentEngine] = None


def get_task_assignment_engine() -> TaskAssignmentEngine:
    """Get singleton task assignment engine."""
    global _task_assignment_engine
    if _task_assignment_engine is None:
        _task_assignment_engine = TaskAssignmentEngine()
    return _task_assignment_engine