from flask import Flask, request, jsonify
import anthropic
from anthropic import HUMAN_PROMPT, AI_PROMPT
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
# Replace with your actual Claude API key
CLAUDE_API_KEY = ''

client = anthropic.Anthropic(
    api_key=CLAUDE_API_KEY,
)

@app.route('/create-test', methods=['GET'])
def create_test():
    difficulty = request.args.get('difficulty')
    text = request.args.get('text')

    if not difficulty or not text:
        return jsonify({"error": "Missing difficulty or text"}), 400

    completion = client.completions.create(
    model="claude-2.1",
    max_tokens_to_sample=300,
    prompt=f"{HUMAN_PROMPT} Creaza un test de 3 intrebari scurte de dificultatea: {difficulty} bazat pe lectia: {text}{AI_PROMPT}",
)

    return jsonify({"response": completion.completion})

if __name__ == '__main__':
    app.run(debug=True)
