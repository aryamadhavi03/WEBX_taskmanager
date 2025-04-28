from datetime import datetime
from bson import ObjectId

class Task:
    STATUS_CHOICES = ['Not Started', 'In Progress', 'On Hold', 'Completed']
    PRIORITY_CHOICES = ['Low', 'Medium', 'High']

    def __init__(self, task_data):
        self.id = str(task_data.get('_id'))
        self.title = task_data.get('title')
        self.description = task_data.get('description')
        self.status = task_data.get('status', 'Not Started')
        self.priority = task_data.get('priority', 'Medium')
        self.deadline = task_data.get('deadline')
        self.created_at = task_data.get('created_at', datetime.utcnow())
        self.updated_at = task_data.get('updated_at')
        self.owner = task_data.get('owner')
        self.assigned_to = task_data.get('assigned_to', [])
        self.tags = task_data.get('tags', [])
        self.collaborators = task_data.get('collaborators', [])

    @staticmethod
    def create_task(title, description, deadline, priority, owner, tags=None):
        """Create a new task"""
        task_data = {
            'title': title,
            'description': description,
            'status': 'Not Started',
            'priority': priority,
            'deadline': deadline,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'owner': owner,
            'assigned_to': [owner],
            'tags': tags or [],
            'collaborators': []
        }
        return task_data

    def update_status(self, new_status):
        """Update task status and timestamp"""
        if new_status not in self.STATUS_CHOICES:
            raise ValueError(f'Invalid status. Must be one of {self.STATUS_CHOICES}')
        return {
            'status': new_status,
            'updated_at': datetime.utcnow()
        }

    def add_tags(self, tags):
        """Add tags to the task"""
        new_tags = [tag for tag in tags if tag not in self.tags]
        if new_tags:
            self.tags.extend(new_tags)
        return {
            'tags': self.tags,
            'updated_at': datetime.utcnow()
        }

    def remove_tag(self, tag):
        """Remove a tag from the task"""
        if tag in self.tags:
            self.tags.remove(tag)
        return {
            'tags': self.tags,
            'updated_at': datetime.utcnow()
        }

    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if not self.deadline:
            return False
        return datetime.utcnow() > datetime.strptime(self.deadline, '%Y-%m-%d')

    @property
    def priority_color(self):
        """Get color code for priority"""
        colors = {
            'Low': '#28a745',    # Green
            'Medium': '#ffc107',  # Yellow
            'High': '#dc3545'     # Red
        }
        return colors.get(self.priority, '#6c757d')  # Default gray