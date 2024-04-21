from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import json
import os
#########
from flask import Flask, request, jsonify
import getpass, os, pymongo, pprint
import pymongo
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.settings import Settings
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
##############


app = Flask(__name__)
app.config['SECRET_KEY'] = ''
socketio = SocketIO(app)

messages_file = 'chat_messages.json'  # File to store chat messages

os.environ["OPENAI_API_KEY"] = ''
ATLAS_CONNECTION_STRING = ('')

# LlamaIndex Settings
Settings.llm = OpenAI()
Settings.embed_model = OpenAIEmbedding(model="text-embedding-ada-002")
sample_data = SimpleDirectoryReader(input_files=["./data/social_engineering.pdf"]).load_data()

# Connect to your Atlas cluster
mongodb_client = pymongo.MongoClient(ATLAS_CONNECTION_STRING)

atlas_vector_search = MongoDBAtlasVectorSearch(
    mongodb_client,
    db_name="llamaindex_db",
    collection_name="test",
    index_name="vector_index__"
)
vector_store_context = StorageContext.from_defaults(vector_store=atlas_vector_search)

# Store data as vector embeddings
vector_store_index = VectorStoreIndex.from_documents(
    sample_data, storage_context=vector_store_context, show_progress=True
)

# Instantiate Atlas Vector Search as a retriever
vector_store_retriever = VectorIndexRetriever(index=vector_store_index, similarity_top_k=5)

# Pass the retriever into the query engine
query_engine = RetrieverQueryEngine(retriever=vector_store_retriever)

@socketio.on('send alert')
def on_alert(data):
    emit('show alert', data, broadcast=True)

def trigger_alert(show, message):
    if show:
        socketio.emit('send alert', {'show': True, 'message': message})

def check_message_security():
    all_messages = read_messages()
    question = f'lease review the following message and determine if it contains any questions or phrases that could specifically expose my credentials or compromise my security, excluding general social interactions like \'how are you?\' or similar. Analyze the content and provide a focused response.Answer YES or NO. Please analyze and provide a response based on the content.: {all_messages}'
    response = query_engine.query(question)
    # print(response)
    if 'YES' in str(response):
        response = query_engine.query("what attack method is used against me in this conversation?: " + all_messages)
        print("\033[91m" + str(response) + "\033[0m")
    else:
        print("\033[92m" + str(response) + "\033[0m")

def load_messages():
    """Load messages from a JSON file."""
    if os.path.exists(messages_file):
        with open(messages_file, 'r') as file:
            return json.load(file)
    return []

def read_messages():
    """Load messages from a JSON file and return them as a string."""
    if os.path.exists(messages_file):
        with open(messages_file, 'r') as file:
            data = json.load(file)
            return json.dumps(data)  # Convert the JSON object to a string and return it
    return "[]" 

def save_message(data):
    """Save a new message to the JSON file."""
    messages = load_messages()
    messages.append(data)
    with open(messages_file, 'w') as file:
        json.dump(messages, file)



@app.route('/')
def index():
    # Serve the chat interface
    return render_template('index.html', messages=load_messages())

@socketio.on('connect')
def on_connect():
    print('Client connected')
    # Load existing messages and emit to the newly connected client
    for message in load_messages():
        emit('chat message', message)

@socketio.on('disconnect')
def on_disconnect():
    print('Client disconnected')

@socketio.on('register user')
def on_register_user(data):
    print(f'User registered: {data["username"]} with color {data["color"]}')
    emit('user connected', data, broadcast=True, include_self=False)

@socketio.on('chat message')
def on_chat_message(data):
    print(f'Received message: "{data["message"]}" from {data["username"]}')
    emit('chat message', data, broadcast=True)
    save_message(data)
    check_message_security()
    trigger_alert(True, "HELP!")


if __name__ == '__main__':
    socketio.run(app, debug=True)