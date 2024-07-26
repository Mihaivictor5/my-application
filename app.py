from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_migrate import Migrate
from flask_cors import CORS
import anthropic
from anthropic import HUMAN_PROMPT, AI_PROMPT
import os
import pdfplumber
import logging
from werkzeug.exceptions import RequestEntityTooLarge

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)
CORS(app)

# Replace with your actual Claude API key
CLAUDE_API_KEY = 'your_claude_api_key'
client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

from models import User, Document

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    documents = Document.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', user=current_user, documents=documents)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            text_content = extract_text_from_pdf(filepath)
            document = Document(filename=filename, user_id=current_user.id, content=text_content)
            db.session.add(document)
            db.session.commit()
            flash('File successfully uploaded', 'success')
            return redirect(url_for('dashboard'))
    return render_template('upload.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf'}

def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + '\n'
    return text

@app.route('/select-document')
@login_required
def select_document():
    documents = Document.query.filter_by(user_id=current_user.id).all()
    return render_template('select_document.html', documents=documents)

@app.route('/choose-test/<int:document_id>', methods=['GET', 'POST'])
@login_required
def choose_test(document_id):
    document = Document.query.get_or_404(document_id)
    if request.method == 'POST':
        test_type = request.form.get('test_type')
        difficulty = request.form.get('difficulty')
        return redirect(url_for('create_test', difficulty=difficulty, text=document.content))
    return render_template('choose_test.html', document=document)

"""@app.route('/create-test', methods=['GET'])
@login_required
def create_test():
    difficulty = request.args.get('difficulty')
    text = request.args.get('text')

    logger.info(f'Received create-test request with difficulty: {difficulty} and text: {text}')

    if not difficulty or not text:
        return jsonify({"error": "Missing difficulty or text"}), 400

    try:
        completion = client.completions.create(
            model="claude-2.1",
            max_tokens_to_sample=300,
            prompt=f"{HUMAN_PROMPT} Creaza un test de 3 intrebari scurte de dificultatea: {difficulty} bazat pe lectia: {text} si spune mi doar intrebarile numerotate si dificultatea{AI_PROMPT}",
        )
        logger.info(f'API response: {completion.completion}')
        return render_template('test_result.html', test=completion.completion)
    except Exception as e:
        logger.error(f'Error calling API: {str(e)}')
        return jsonify({"error": "Failed to generate test"}), 500"""

@app.route('/create-test', methods=['GET'])
@login_required
def create_test():
    global generated_test
    
    difficulty = request.args.get('difficulty')
    text = request.args.get('text')
    test_type = request.args.get('type')

    if not difficulty or not text or not test_type:
        return jsonify({"error": "Missing difficulty, text, or test type"}), 400

    prompt = f"{HUMAN_PROMPT} Creeaza o intrebare de test de tip {test_type}, de dificultatea: {difficulty}, bazata pe lectia: {text} ,inainte de intrebare scrie *, iar dupa intrebare scrie # (ADICA LA FINALUL CERINTEI) {AI_PROMPT}"

    try:
        completion = client.completions.create(
            model="claude-2.1",
            max_tokens_to_sample=200,
            prompt=prompt,
        )

        response_text = completion.completion.strip()
        test_start_index = response_text.find("*")
        test_end_index = response_text.rfind("#")
        generated_test = response_text[test_start_index+1:test_end_index].strip()

        return jsonify({"response": generated_test})

    except Exception as e:
        print(f"Error creating test: {str(e)}")
        return jsonify({"error": "Error creating test. Please try again."}), 500
    








@app.route('/list-uploads')
@login_required
def list_uploads():
    uploads = os.listdir(app.config['UPLOAD_FOLDER'])
    upload_info = []
    for upload in uploads:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], upload)
        size = os.path.getsize(file_path)
        upload_info.append({'filename': upload, 'size': size})
    return render_template('list_uploads.html', uploads=upload_info)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    flash('File is too large. Maximum size allowed is 50MB.', 'danger')
    return redirect(request.url)

if __name__ == '__main__':
    app.run(debug=True)
