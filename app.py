from flask import Flask, send_from_directory, request, jsonify
import os

app = Flask(__name__, static_folder='frontend')

@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    
    # 简单的模拟回复逻辑
    return jsonify({
        'reply': f'后端已收到消息: {user_message}'
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
