# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from bson.objectid import ObjectId
from datetime import datetime
import os

# Import models
from models.user import User
from models.task import Task

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Replace this with a secure random key

app.config['MONGO_URI'] = 'mongodb://localhost:27017/task_manager'
mongo = PyMongo(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Use the User model from models/user.py

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# Home Route
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        if password != confirm_password:
            return render_template('signup_new.html', error='Passwords do not match!')

        # Check if username or email already exists
        existing_user = mongo.db.users.find_one({'$or': [
            {'username': username},
            {'email': email}
        ]})
        if existing_user:
            error = 'Username or email already exists!'
            return render_template('signup_new.html', error=error)

        # Create new user
        user_data = User.create_user(username, email, password, role)
        mongo.db.users.insert_one(user_data)
        return redirect(url_for('login'))
    return render_template('signup_new.html')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_data = mongo.db.users.find_one({'email': email})

        if not user_data:
            return render_template('login_new.html', error='User not found!')

        user = User(user_data)
        if user.check_password(password):
            login_user(user)
            # Update last login time
            mongo.db.users.update_one(
                {'_id': ObjectId(user.id)},
                {'$set': user.update_last_login()}
            )
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        return render_template('login_new.html', error='Invalid password!')
    return render_template('login_new.html')


# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Admin Dashboard
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return 'Access denied'
    users = list(mongo.db.users.find({'role': 'employee'}))
    tasks = list(mongo.db.tasks.find())
    
    # Calculate task statistics
    stats = {
        'total': len(tasks),
        'completed': len([t for t in tasks if t.get('status') == 'Completed']),
        'pending': len([t for t in tasks if t.get('status') != 'Completed'])
    }
    
    return render_template('admin_dashboard.html', users=users, tasks=tasks, stats=stats)

# Assign Task

@app.route('/assign', methods=['POST'])
@login_required
def assign_task():
    if current_user.role != 'admin':
        return 'Access denied'
    title = request.form['title']
    description = request.form['description']
    username = request.form['username']
    due_date = request.form['due_date']
    priority = request.form.get('priority', 'Medium')
    
    # Get user ID from username
    assigned_user = mongo.db.users.find_one({'username': username})
    if not assigned_user:
        return 'User not found', 404
        
    task_data = Task.create_task(
        title=title,
        description=description,
        deadline=due_date,
        priority=priority,
        owner=str(assigned_user['_id']),
        tags=[]
    )
    # Ensure assigned_to field is properly set
    task_data['assigned_to'] = [str(assigned_user['_id'])]
    mongo.db.tasks.insert_one(task_data)
    return redirect(url_for('admin_dashboard'))


# User Dashboard
@app.route('/user')
@login_required
def user_dashboard():
    if current_user.role != 'employee':
        return 'Access denied'

    # Get task statistics
    all_tasks = list(mongo.db.tasks.find({
        '$or': [
            {'owner': current_user.id},
            {'owner': str(current_user.id)},
            {'assigned_to': {'$in': [current_user.id, str(current_user.id)]}},
            {'collaborators': {'$in': [current_user.id, str(current_user.id)]}}
        ]
    }))

    stats = {
        'total': len(all_tasks),
        'completed': len([t for t in all_tasks if t['status'] == 'Completed']),
        'pending': len([t for t in all_tasks if t['status'] != 'Completed'])
    }

    # Filter tasks based on query parameters
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    search_query = request.args.get('search')

    filtered_tasks = all_tasks
    if status_filter and status_filter.strip():
        status_filter = status_filter.strip().lower()
        filtered_tasks = [t for t in filtered_tasks if t.get('status', '').lower() == status_filter]
    if priority_filter:
        filtered_tasks = [t for t in filtered_tasks if t['priority'] == priority_filter]
    if search_query:
        filtered_tasks = [t for t in filtered_tasks if
            search_query.lower() in t['title'].lower() or
            search_query.lower() in t.get('description', '').lower()]

    active_tasks = [t for t in filtered_tasks if t['status'] != 'Completed']
    completed_tasks = [t for t in filtered_tasks if t['status'] == 'Completed']

    return render_template('user_dashboard.html',
                         user=current_user,
                         stats=stats,
                         active_tasks=active_tasks,
                         completed_tasks=completed_tasks)


# Update Task Status
@app.route('/update_task/<task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    new_status = request.form['status']
    mongo.db.tasks.update_one({'_id': ObjectId(task_id)}, {'$set': {'status': new_status}})
    return redirect(url_for('user_dashboard'))

# Create Task
@app.route('/task/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        deadline = request.form['deadline']
        priority = request.form['priority']
        tags = [tag.strip() for tag in request.form['tags'].split(',') if tag.strip()]

        task_data = Task.create_task(
            title=title,
            description=description,
            deadline=deadline,
            priority=priority,
            owner=current_user.id,
            tags=tags
        )
        mongo.db.tasks.insert_one(task_data)
        return redirect(url_for('user_dashboard'))

    return render_template('task_form.html', task=None)

# Edit Task
@app.route('/task/edit/<task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task_data = mongo.db.tasks.find_one({'_id': ObjectId(task_id)})
    if not task_data:
        return 'Task not found', 404

    task = Task(task_data)
    # Allow admin or task owner/collaborator to edit
    if not current_user.is_admin and task.owner != current_user.id and current_user.id not in task.collaborators:
        return 'Access denied', 403

    if request.method == 'POST':
        updated_data = {
            'title': request.form['title'],
            'description': request.form['description'],
            'deadline': request.form['deadline'],
            'priority': request.form['priority'],
            'status': request.form['status'],
            'tags': [tag.strip() for tag in request.form['tags'].split(',') if tag.strip()],
            'updated_at': datetime.utcnow()
        }
        mongo.db.tasks.update_one({'_id': ObjectId(task_id)}, {'$set': updated_data})
        return redirect(url_for('admin_dashboard' if current_user.is_admin else 'user_dashboard'))
    
    return render_template('task_form.html', task=task)

    return render_template('task_form.html', task=task_data)

# Delete Task
@app.route('/task/delete/<task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = mongo.db.tasks.find_one({'_id': ObjectId(task_id)})
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Convert task to Task model instance for consistent property access
    task_model = Task(task)
    
    # Check if user has permission to delete (owner, admin, or assigned user)
    if current_user.is_admin or task_model.owner == str(current_user.id) or \
       str(current_user.id) in task_model.assigned_to:
        mongo.db.tasks.delete_one({'_id': ObjectId(task_id)})
        return redirect(request.referrer or url_for('admin_dashboard'))
    
    return jsonify({'error': 'Permission denied'}), 403

@app.route('/kanban')
@login_required
def kanban_board():
    tasks = list(mongo.db.tasks.find({
        '$or': [
            {'owner': current_user.id},
            {'assigned_to': current_user.id},
            {'collaborators': current_user.id}
        ]
    }))
    return render_template('kanban.html', tasks=tasks)

@app.route('/task/share/<task_id>', methods=['POST'])
@login_required
def share_task(task_id):
    task_data = mongo.db.tasks.find_one({'_id': ObjectId(task_id)})
    if not task_data or task_data['owner'] != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    collaborator_email = request.form['email']
    collaborator = mongo.db.users.find_one({'email': collaborator_email})
    if not collaborator:
        return jsonify({'error': 'User not found'}), 404

    task = Task(task_data)
    update_data = task.add_collaborator(str(collaborator['_id']))
    mongo.db.tasks.update_one(
        {'_id': ObjectId(task_id)},
        {'$set': update_data}
    )
    return jsonify({'message': 'Collaborator added successfully'})

if __name__ == '__main__':
    app.run(debug=True)
