from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
from waitress import serve
import json

PORT = 8000
app = Flask(__name__)
rules_manager = None
rc_manager = None
CORS(app)  # This will enable CORS for all routes

def create_proxy_server(rc_manager):
    @app.route('/')
    def serve_html():
        with open('rc_search.html', 'r') as file:
            content = file.read()
            content = content.replace('{{ROCKET_CHAT_URL}}', rc_manager._SERVER_ADDRESS)
        return content

    @app.route('/api/subscriptions', methods=['GET'])
    def get_subscriptions():
        url = f"{rc_manager._SERVER_ADDRESS}/api/v1/subscriptions.get"
        headers = {
            'X-User-Id': rc_manager._ROCKET_USER_ID,
            'X-Auth-Token': rc_manager._ROCKET_TOKEN,
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        subscriptions = data.get('update', [])
        return jsonify({'subscriptions': subscriptions})

    @app.route('/api/search', methods=['GET'])
    def search_messages():
        room_id = request.args.get('roomId')
        search_text = request.args.get('searchText')
        
        url = f"{rc_manager._SERVER_ADDRESS}/api/v1/chat.search"
        headers = {
            'X-User-Id': rc_manager._ROCKET_USER_ID,
            'X-Auth-Token': rc_manager._ROCKET_TOKEN,
        }
        params = {
            'roomId': room_id,
            'searchText': search_text,
        }
        response = requests.get(url, headers=headers, params=params)
        return jsonify(response.json())

    @app.route('/shutdown', methods=['GET'])
    def shutdown():
        import os
        import signal
        os.kill(os.getpid(), signal.SIGINT)
        return 'Server shutting down...'
    
    @app.route('/api/debug', methods=['GET'])
    def debug():
        content = f"""
<pre>rc_manager.unread_messages\n{json.dumps(rc_manager.unread_messages, indent=4, sort_keys=True)}\n 
rules_manager.unread_counts\n{json.dumps(rules_manager.unread_counts, indent=4, sort_keys=True)}</pre>
"""
        return content
    
    @app.route('/api/subscriptions', methods=['GET'])
    def subscriptions():
        return f"<pre>{json.dumps(rc_manager.get_all_subscriptions(), indent=4, sort_keys=True)}</pre>"


def get_proxy_url():
    return f"http://localhost:{PORT}"

def run_proxy_server(p_rc_manager, p_rules_manager):
    global rc_manager, rules_manager
    rc_manager = p_rc_manager
    rules_manager = p_rules_manager
    proxy_app = create_proxy_server(p_rc_manager)

    serve(app, host="0.0.0.0", port=PORT)
    #proxy_app.run(debug=False, port=PORT, use_reloader=False)
