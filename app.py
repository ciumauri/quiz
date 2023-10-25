from flask import Flask, jsonify
import json, random

app = Flask(__name__)

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
    def __init__(self, filename):
        self.questions = []
        with open(filename, "r") as f:
            data = json.load(f)
            self.questions = data['questions']

    def select_questions(self, strategy_name, **criteria):
        strategy = StrategyFactory.create_strategy(strategy_name)
        return strategy.select_questions(self.questions, **criteria)

@app.route('/questions')
def all_questions():
    data_manager = DataManager("quiz.json")
    questions = data_manager.select_questions('all')  # Seleciona todas as questões
    return jsonify(questions)

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

class QuizInterface:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.correct_answers = 0  # Initialize a counter for correct answers

    def start(self):
        print("Bem-vindo ao Quiz!")

        while True:
            print("\nEscolha uma opção:")
            print("1. Perguntas por dificuldade")
            print("2. Perguntas por tema")
            print("3. Perguntas aleatórias")
            print("4. Sair")

            choice = input("Digite o número da opção desejada: ")

            if choice == '1':
                self.select_questions_by_difficulty()
            elif choice == '2':
                self.select_questions_by_theme()
            elif choice == '3':
                self.select_random_questions()
            elif choice == '4':
                break
            else:
                print("Opção inválida. Tente novamente.")

    def select_questions_by_difficulty(self):
        difficulty = input("Digite a dificuldade desejada: ")
        questions = self.data_manager.select_questions('difficulty', difficulty=int(difficulty))
        self.display_questions(questions)

    def select_questions_by_theme(self):
        theme = input("Digite o tema desejado: ")
        questions = self.data_manager.select_questions('theme', theme=theme)
        self.display_questions(questions)

    def select_random_questions(self):
        count = input("Digite o número de perguntas desejado: ")
        questions = self.data_manager.select_questions('random', count=int(count))
        self.display_questions(questions)

    def display_questions(self, questions):
        for question in questions:
            print("\nPergunta:", question['question'])

            options = question['options']
            correct_answer = question['ca']  # Usar 'ca' (chave correta da resposta)

            for key, option in options.items():
                print(f"{key}. {option}")

            user_answer = input("Escolha a opção correta (a, b, c, d, etc.): ").lower()

            if user_answer in options:
                if options[user_answer] == options[correct_answer]:
                    print("Resposta correta!")
                    self.correct_answers += 1  # Increment the correct answer count
                    print(f"Respostas corretas {self.correct_answers}")
                else:
                    print(f"Resposta incorreta. A resposta correta era a opção {correct_answer}.")
                    print(f"Respostas corretas {self.correct_answers}")
            else:
                print("Opção inválida. Tente novamente.")

if __name__ == '__main__':
    data_manager = DataManager("quiz.json")
    quiz_interface = QuizInterface(data_manager)
    quiz_interface.start()
