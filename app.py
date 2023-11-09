from flask import Flask, render_template, url_for, request, g, redirect, session, jsonify
from flask_session import Session
import json
import random
import os
from database import connect_to_database, getDatabase
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

# Estratégia de seleção por aleatoriedade
class RandomSelection(QuestionSelectionStrategy):
    def select_questions(self, questions, **criteria):
        count = criteria.get('count', None)
        if count is not None:
            return random.sample(questions, count)
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
    # instance = None
    def __init__(self, filename):
        with open(filename, "r") as f:
            data = json.load(f)
            self.questions = data['questions']

    # __new__()

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
    if request.method == "POST":
        name = request.form['name']
        password = request.form['password']
        db = getDatabase()
        cursor = db.execute("select * from users where name = ?", [name])
        personfromdatabase = cursor.fetchone()
        if personfromdatabase:
            if check_password_hash(personfromdatabase['password'], password):
                session['user'] = personfromdatabase['name']
                return redirect(url_for('quiz'))
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

        hashed_password = generate_password_hash(password, method='sha256')
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

# Quiz
# Quiz
@app.route('/quiz', methods=["GET", "POST"])
def quiz():
    user = get_current_user()
    error = None

    if user is None:
        return redirect(url_for('login'))

    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('all')

    current_question_index = int(request.form.get('current_question_index', 0))

    if request.method == "POST":
        user_answer = request.form.get(f'question{current_question_index}')

        if user_answer is not None and user_answer != "":
            correct_answer = questions[current_question_index]['ca']

            if user_answer == correct_answer:
                # Incrementar a contagem de respostas corretas na sessão
                session['correct_answers'] = session.get('correct_answers', 0) + 1

            current_question_index += 1
        else:
            # O usuário não fez uma seleção, exibindo uma mensagem de erro
            error = "Por favor, selecione uma opção antes de avançar para a próxima pergunta."
            current_question = questions[current_question_index]
            current_question['correct_answer'] = questions[current_question_index]['ca']
            return render_template("quiz.html", user=user, current_question=current_question, current_question_index=current_question_index, error=error)

    if 0 <= current_question_index < len(questions):
        current_question = questions[current_question_index]
        current_question['correct_answer'] = questions[current_question_index]['ca']
    else:
        # Redirecionar para a página de conclusão do quiz
        return redirect(url_for('quiz_complete'))

    return render_template("quiz.html", user=user, current_question=current_question, current_question_index=current_question_index, error=error)

# Rota para exibir quando o quiz estiver completo
# Rota para exibir quando o quiz estiver completo
@app.route('/quiz_complete')
def quiz_complete():
    user = get_current_user()
    correct_answers = session.get('correct_answers', 0)
    data_manager = DataManager("quiz.json")
    total_questions = len(data_manager.questions)

    # Calcular a porcentagem de acertos
    percentage_correct = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

    print(f"Total de acertos: {correct_answers}")

    session.pop('correct_answers', None)

    return render_template("quiz_complete.html", correct_answers=correct_answers, total_questions=total_questions, user=user, percentage_correct=percentage_correct)

@app.route('/questions/difficulty/<int:difficulty>')
def questions_by_difficulty(difficulty):
    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('difficulty', difficulty=difficulty)  # Use 'difficulty' para questões por dificuldade
    return jsonify(questions)

@app.route('/questions/theme/<theme>')
def questions_by_theme(theme):
    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('theme', theme=theme)  # Use 'theme' para questões por tema
    return jsonify(questions)

@app.route('/questions/random/<int:count>')
def random_questions(count):
    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('random', count=count)  # Use 'random' para seleção aleatória
    return jsonify(questions)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
