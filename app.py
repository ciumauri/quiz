from flask import Flask, render_template, url_for, request, g, redirect, session
from flask_session import Session
import json
import random
import os
from database import getDatabase
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Strategy para seleção de perguntas
class QuestionSelectionStrategy:
    def select_questions(self, questions, **criteria):
        return questions

# Estratégia de seleção por dificuldade
class DifficultySelection(QuestionSelectionStrategy):
    def select_questions(self, questions, **criteria):
        difficulty = criteria.get('difficulty', None)
        if difficulty is not None:
            return [q for q in questions if q['difficulty'] == difficulty]
        else:
            return questions

# Estratégia de seleção por tema
class ThemeSelection(QuestionSelectionStrategy):
    def select_questions(self, questions, **criteria):
        theme = criteria.get('theme', None)
        if theme is not None:
            return [q for q in questions if q['theme'] == theme]
        else:
            return questions

class RandomSelection(QuestionSelectionStrategy):
    def select_questions(self, questions, **criteria):
        count = criteria.get('count', None)
        if count is not None:
            random.shuffle(questions)
            return questions[:count]
        else:
            return questions

# Factory para criar estratégias com base no critério
class StrategyFactory:
    @staticmethod
    def create_strategy(strategy_name):
        if strategy_name == 'difficulty':
            return DifficultySelection()
        elif strategy_name == 'theme':
            return ThemeSelection()
        elif strategy_name == 'random':
            return RandomSelection()
        elif strategy_name == 'all':  # Adicione a estratégia "all" para selecionar todas as questões
            return QuestionSelectionStrategy()
        # Adicione mais estratégias aqui, se necessário
        else:
            return QuestionSelectionStrategy()

# Singleton para carregar dados
class DataManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, filename):
        self.questions = []
        with open(filename, "r") as f:
            data = json.load(f)
            self.questions = data['questions']

    def select_questions(self, strategy_name, **criteria):
        strategy = StrategyFactory.create_strategy(strategy_name)
        return strategy.select_questions(self.questions, **criteria)

############################################################################################################################

@app.teardown_appcontext
def close_database(error):
    if hasattr(g, 'quizapp_db'):
        g.quizapp_db.close()

def get_current_user():
    user_result = None
    if 'user' in session:
        user = session['user']
        db = getDatabase()
        user_cursor = db.execute("select * from users where name = ?", [user])
        user_result = user_cursor.fetchone()
    return user_result

# Home
@app.route('/')
def index():
    user = get_current_user()
    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('all')  # Use a estratégia 'all' para selecionar todas as perguntas
    return render_template("home.html", user=user, questions=questions)

# Login
@app.route('/login', methods=["POST", "GET"])
def login():
    user = get_current_user()
    error = None
    session.pop('destination', None)  # Obter e remover a página de destino da sessão
    if request.method == "POST":
        name = request.form['name']
        password = request.form['password']
        db = getDatabase()
        cursor = db.execute("select * from users where name = ?", [name])
        personfromdatabase = cursor.fetchone()
        if personfromdatabase:
            if check_password_hash(personfromdatabase['password'], password):
                session['user'] = personfromdatabase['name']
                return redirect(url_for('index'))
            else:
                error = "Usuário ou senha inválidos. Tente novamente!"
                return render_template('login.html', error = error)
        else:
            error = "Usuário ou senha inválidos. Tente novamente!"
            return redirect(url_for('login'))

    return render_template("login.html", user = user, error = error)

# Register
@app.route('/register', methods=["POST", "GET"])
def register():
    user = get_current_user()
    error = None
    if request.method == "POST":
        db = getDatabase()
        name = request.form["name"]
        password = request.form["password"]

        # Verificar campos vazios
        if not name or not password:
            error = "Preencha todos os campos."
            return render_template("register.html", error=error)

        # Verificar senha menor que 6 caracteres
        if len(password) < 6:
            error = "A senha deve ter pelo menos 6 caracteres."
            return render_template("register.html", error=error)

        # Verificar usuario existente
        user_fetcing_cursor = db.execute("select * from users where name = ?", [name])
        existing_user = user_fetcing_cursor.fetchone()

        if existing_user:
            error = "Usuário existente, por favor escolha um usuário diferente."
            return render_template("register.html", error = error)

        hashed_password = generate_password_hash(password)
        db.execute("insert into users (name, password, user, admin) values (?, ?, ?, ?)", [name, hashed_password, 0, 0])
        db.commit()
        session['user'] = name
        return redirect(url_for('index'))

    return render_template("register.html", user = user)

# All Users
@app.route('/allusers', methods=["POST", "GET"])
def allusers():
    user = get_current_user()
    db = getDatabase()
    user_cursor = db.execute("select * from users")
    allusers = user_cursor.fetchall()
    return render_template("allusers.html", user =  user, allusers = allusers)

# Promoção
@app.route("/promote/<int:id>", methods=["POST","GET"])
def promote(id):
    user = get_current_user()
    if request.method == "GET":
        db = getDatabase()
        db.execute("update users set user = 1 where id = ?", [id])
        db.commit()
        return redirect(url_for('allusers'))
    return render_template("allusers.html", user =  user, allusers = allusers)

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

def process_question_response(user_answer, questions, current_question_index, redirect_route, theme=None, count=None, difficulty=None):
    if user_answer is not None and user_answer == "":
        correct_answer = questions[current_question_index]['ca']

        if user_answer == correct_answer:
            session['correct_answers'] = session.get('correct_answers', 0) + 1
        else:
            wrong_questions = session.get('wrong_questions', [])
            wrong_question_data = {
                'question': questions[current_question_index]['question'],
                'user_answer_key': user_answer,
                'user_answer_value': questions[current_question_index]['options'][user_answer],
                'correct_answer_key': correct_answer,
                'correct_answer_value': questions[current_question_index]['options'][correct_answer],
            }
            wrong_questions.append(wrong_question_data)
            session['wrong_questions'] = wrong_questions

        current_question_index += 1
    else:
        error = "Por favor, selecione uma opção antes de avançar para a próxima pergunta."
        current_question = questions[current_question_index]
        current_question['correct_answer'] = questions[current_question_index]['ca']
        if redirect_route == 'quiz':
            return render_template("quiz.html", current_question=current_question, current_question_index=current_question_index, questions=questions, error=error)
        elif redirect_route == 'random_questions':
            return render_template("random.html", current_question=current_question, current_question_index=current_question_index, questions=questions, error=error, count=count)
        elif redirect_route == 'questions_by_theme':
            return render_template("by_theme.html", current_question=current_question, current_question_index=current_question_index, questions=questions, error=error, theme=theme)
        elif redirect_route == 'questions_by_difficulty':
            return render_template("by_difficulty.html", current_question=current_question, current_question_index=current_question_index, questions=questions, error=error, difficulty=difficulty)

    if current_question_index >= len(questions):
        if redirect_route in ['quiz', 'random_questions']:
            return redirect(url_for('quiz_complete'))
        elif redirect_route == 'questions_by_theme':
            theme_questions = session.get('theme_questions', [])
            theme_questions.extend(questions)  # Adiciona as perguntas do tema à lista
            session['theme_questions'] = theme_questions
        elif redirect_route == 'questions_by_difficulty':
            difficulty_questions = session.get('difficulty_questions', [])
            difficulty_questions.extend(questions)  # Adiciona as perguntas por dificuldade à lista
            session['difficulty_questions'] = difficulty_questions
        return redirect(url_for('quiz_complete'))

    current_question = questions[current_question_index]
    current_question['correct_answer'] = questions[current_question_index]['ca']

    if redirect_route == 'quiz':
        return render_template("quiz.html", current_question=current_question, current_question_index=current_question_index, questions=questions)
    elif redirect_route == 'random_questions':
        return render_template("random.html", current_question=current_question, current_question_index=current_question_index, questions=questions, count=count)
    elif redirect_route == 'questions_by_theme':
        return render_template("by_theme.html", current_question=current_question, current_question_index=current_question_index, questions=questions, theme=theme)
    elif redirect_route == 'questions_by_difficulty':
        return render_template("by_difficulty.html", current_question=current_question, current_question_index=current_question_index, questions=questions, difficulty=difficulty)


@app.route('/quiz', methods=["GET", "POST"])
def quiz():
    user = get_current_user()

    if user is None:
        return redirect(url_for('login'))

    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('all')

    # Armazena as perguntas na sessão se ainda não estiverem armazenadas
    if 'questions' not in session:
        session['questions'] = questions

    current_question_index = int(request.form.get('current_question_index', 0))

    if 'total_questions' not in session:
        session['total_questions'] = len(questions)

    if request.method == "POST":
        user_answer = request.form.get(f'question{current_question_index}')
        response = process_question_response(user_answer, questions, current_question_index, 'all')
        if response is not None:
            return response
        else:
            current_question_index += 1  # Avança para a próxima pergunta

    if 0 <= current_question_index < len(questions):
        current_question = questions[current_question_index]
        current_question['correct_answer'] = questions[current_question_index]['ca']
    else:
        return redirect(url_for('quiz_complete'))

    return render_template("quiz.html", user=user, current_question=current_question, current_question_index=current_question_index, questions=questions, total_questions=len(questions))

@app.route('/questions/difficulty/<int:difficulty>', methods=['GET', 'POST'])
def questions_by_difficulty(difficulty):
    user = get_current_user()

    if user is None:
        return redirect(url_for('login'))

    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('difficulty', difficulty=difficulty)

    # Armazena as perguntas na sessão se ainda não estiverem armazenadas
    if 'questions' not in session:
        session['questions'] = questions

    current_question_index = int(request.form.get('current_question_index', 0))

    if 'total_questions' not in session:
        session['total_questions'] = len(questions)

    if request.method == "POST":
        user_answer = request.form.get(f'question{current_question_index}')
        response = process_question_response(user_answer, questions, current_question_index, 'difficulty', difficulty=difficulty)
        if response is not None:
            return response
        else:
            current_question_index += 1  # Avança para a próxima pergunta

    if 0 <= current_question_index < len(questions):
        current_question = questions[current_question_index]
        current_question['correct_answer'] = questions[current_question_index]['ca']
    else:
        # Redireciona para a página de resultados (quiz_complete) após a última pergunta
        return redirect(url_for('quiz_complete'))

    return render_template("by_difficulty.html", user=user, current_question=current_question, current_question_index=current_question_index, questions=questions, total_questions=len(questions), difficulty=difficulty)

@app.route('/questions/theme/<theme>', methods=['GET', 'POST'])
def questions_by_theme(theme):
    user = get_current_user()

    if user is None:
        return redirect(url_for('login'))

    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('theme', theme=theme)

    # Armazena as perguntas na sessão se ainda não estiverem armazenadas
    if 'questions' not in session:
        session['questions'] = questions

    current_question_index = int(request.form.get('current_question_index', 0))

    if 'total_questions' not in session:
        session['total_questions'] = len(questions)

    if request.method == "POST":
        user_answer = request.form.get(f'question{current_question_index}')
        response = process_question_response(user_answer, questions, current_question_index, 'theme', theme=theme)
        if response is not None:
            return response
        else:
            current_question_index += 1  # Avança para a próxima pergunta    
    
    if 0 <= current_question_index < len(questions):
        current_question = questions[current_question_index]
        current_question['correct_answer'] = questions[current_question_index]['ca']
    else:
        # Redireciona para a página de resultados (quiz_complete) após a última pergunta
        return redirect(url_for('quiz_complete'))

    return render_template("by_theme.html", user=user, current_question=current_question, current_question_index=current_question_index, questions=questions, total_questions=len(questions), theme=theme)

@app.route('/questions/random/<int:count>', methods=["GET", "POST"])
def random_questions(count):
    user = get_current_user()

    if user is None:
        return redirect(url_for('login'))

    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('random', count=count)

    # Armazena as perguntas na sessão se ainda não estiverem armazenadas
    if 'questions' not in session:
        session['questions'] = questions

    current_question_index = int(request.form.get('current_question_index', 0))

    if 'total_questions' not in session:
        session['total_questions'] = len(questions)

    if request.method == "POST":
        user_answer = request.form.get(f'question{current_question_index}')
        response = process_question_response(user_answer, questions, current_question_index, 'random', count=count)
        if response is not None:
            return response
        else:
            current_question_index += 1  # Avança para a próxima pergunta 

    if 0 <= current_question_index < len(questions):
        current_question = questions[current_question_index]
        current_question['correct_answer'] = questions[current_question_index]['ca']
    else:
        # Redireciona para a página de resultados (quiz_complete) após a última pergunta
        return redirect(url_for('quiz_complete'))

    # Adicione um retorno válido no final da função
    return render_template("random.html", user=user, current_question=current_question, current_question_index=current_question_index, questions=questions, total_questions=len(questions))

@app.route('/quiz_complete')
def quiz_complete():
    user = get_current_user()
    correct_answers = session.get('correct_answers', 0)  # Obtém o número de respostas corretas da sessão

    # Verifica se 'questions' está na sessão
    if 'questions' not in session:
        # Redireciona para a página inicial caso 'questions' não esteja na sessão
        return redirect(url_for('index'))

    total_questions = len(session['questions'])  # Obtém o total de perguntas feitas

    # Calcula a porcentagem de respostas corretas
    percentage_correct = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

    # Limpa o número de respostas corretas da sessão após exibi-lo
    session.pop('correct_answers', None)
    session.pop('questions', None)  # Limpa as perguntas da sessão

    wrong_questions = session.get('wrong_questions', [])
    session.pop('wrong_questions', None)  # Limpa a lista de perguntas erradas da sessão

    return render_template("quiz_complete.html", user=user, correct_answers=correct_answers, total_questions=total_questions, percentage_correct=percentage_correct, wrong_questions=wrong_questions)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
