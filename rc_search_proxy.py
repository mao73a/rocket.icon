from flask import Flask, request, jsonify, send_from_directory
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes

# Your Rocket.Chat credentials
SERVER_ADDRESS = "https://chat.czk.comarch.com"
USER_ID = "Yme82NmFkeZu5s9kh"
USER_TOKEN = "Se9BYjNkhJRbDzvrQpCJaBN6olOUJFaqw2nE9X_o49U"

@app.route('/')
def serve_html():
    with open('rc_search.html', 'r') as file:
        content = file.read()
        content = content.replace('{{ROCKET_CHAT_URL}}', SERVER_ADDRESS)
    return content

@app.route('/api/subscriptions', methods=['GET'])
def get_subscriptions():
    url = f"{SERVER_ADDRESS}/api/v1/subscriptions.get"
    headers = {
        'X-User-Id': USER_ID,
        'X-Auth-Token': USER_TOKEN,
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    print("Subscriptions data:", data)  # Keep this for debugging
    
    # Extract the 'update' array if it exists, otherwise return an empty list
    subscriptions = data.get('update', [])
    return jsonify({'subscriptions': subscriptions})

@app.route('/api/search', methods=['GET'])
def search_messages():
    room_id = request.args.get('roomId')
    search_text = request.args.get('searchText')
    
    url = f"{SERVER_ADDRESS}/api/v1/chat.search"
    headers = {
        'X-User-Id': USER_ID,
        'X-Auth-Token': USER_TOKEN,
    }
    params = {
        'roomId': room_id,
        'searchText': search_text,
    }
    response = requests.get(url, headers=headers, params=params)
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(debug=True, port=8000)