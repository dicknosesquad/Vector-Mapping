# app.py
from flask import Flask, render_template, request, jsonify # type: ignore
from flask_sqlalchemy import SQLAlchemy # type: ignore
from datetime import datetime
from werkzeug.security import generate_password_hash # type: ignore
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user # type: ignore

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///content_calendar.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    subscription_status = db.Column(db.String(20), default='free')
    contents = db.relationship('Content', backref='author', lazy=True)

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='draft')
    engagement_score = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('dashboard.html')
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({'message': 'Registration successful'})

@app.route('/content/generate', methods=['POST'])
@login_required
def generate_content():
    data = request.get_json()
    # Here you would integrate with OpenAI or similar API to generate content
    # This is a simplified example
    generated_content = {
        'title': f"Generated content for {data['topic']}",
        'content': f"AI-generated content about {data['topic']}...",
        'platform': data['platform']
    }
    return jsonify(generated_content)

@app.route('/content/schedule', methods=['POST'])
@login_required
def schedule_content():
    data = request.get_json()
    content = Content(
        title=data['title'],
        content=data['content'],
        platform=data['platform'],
        scheduled_date=datetime.fromisoformat(data['scheduled_date']),
        user_id=current_user.id
    )
    db.session.add(content)
    db.session.commit()
    return jsonify({'message': 'Content scheduled successfully'})

@app.route('/analytics')
@login_required
def analytics():
    contents = Content.query.filter_by(user_id=current_user.id).all()
    analytics_data = {
        'total_posts': len(contents),
        'engagement_rate': sum(c.engagement_score for c in contents) / len(contents) if contents else 0,
        'platform_distribution': {}
    }
    return jsonify(analytics_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# templates/base.html

