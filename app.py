import os
import shutil
import flask
from flask import Flask, request, jsonify, request, Response, render_template
from llama_index import GPTVectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage, LLMPredictor, ServiceContext
from langchain import OpenAI
from flask_cors import CORS # Import the library
from creds import API_KEY
import openai
from hellosign_sdk import HSClient
from flask import Flask, request, jsonify, render_template, redirect, url_for
# ... (your existing imports)

import json

import logging

from creds import API_KEY, HELLOSIGN_API_KEY, client_id


# Initialize logging
logging.basicConfig(level=logging.INFO)


app = Flask(__name__)

CORS(app)  # Enable CORS for the app


DATA_DIR = 'data'

os.environ['OPENAI_API_KEY']  = API_KEY
openai.api_key = API_KEY


client = HSClient(api_key=HELLOSIGN_API_KEY)


# Assume this function is called every time a message is sent or received
def cache_message(email, message):
    if email in session:
        session[email].append(message)
    else:
        session[email] = [message]

def save_sign_urls(index_name, emails, signatures):
    cn = index_name.replace(".pdf", "")
    folder_path = os.path.join("data", cn)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    json_file_path = os.path.join(folder_path, "sign_data.json")

    existing_data = {}
    i = 0
    for signature in signatures:
        signature_id = signature.signature_id
        sign_url = client.get_embedded_object(signature_id).sign_url
        existing_data[emails[i]['email_address']] = {
            "sign_url": sign_url,
        }
        i += 1
    
    with open(json_file_path, 'w') as f:
        json.dump(existing_data, f)

def save_to_json(index_name, email, chat_history=None):
    cn = index_name.replace(".pdf", "")
    folder_path = os.path.join("data", cn)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    
    json_file_path = os.path.join(folder_path, "sign_data.json")

    existing_data = {}
    print(existing_data)
    try:
        with open(json_file_path, 'r') as f:
            existing_data = json.load(f)

    except Exception as e:
        print(e)
    print(existing_data)
    if chat_history:
        existing_data[email].update({"chat_history": chat_history})

    with open(json_file_path, 'w') as f:
        json.dump(existing_data, f)

def create_response(status_code, message, isError, result):
    return jsonify({
        "statusCode": status_code,
        "message": message,
        "isError": isError,
        "result": result
    }), status_code

def insert_file(file, course_name):
    file_dir = os.path.join(DATA_DIR, course_name.replace(".pdf",""))
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)  # Create a new directory for the file
    else :
        shutil.rmtree(file_dir)
        os.mkdir(file_dir)  # Create a new directory for the file

    filename = file.filename
    
    filepath = os.path.join(file_dir, filename)
    file.save(filepath)
    document = SimpleDirectoryReader(file_dir).load_data()
    index = GPTVectorStoreIndex.from_documents(document)  # Store new index
    index.storage_context.persist(file_dir)


def load_index(course_name):
    DIRECTORY = "data"
    storage_path = os.path.join(DIRECTORY, course_name.replace(".pdf",""))
    # if os.path.exists(storage_path):
        # rebuild storage context
    storage_context = StorageContext.from_defaults(persist_dir=storage_path)
    # load index
    index = load_index_from_storage(storage_context)
    return index  # Load the index

def queryFile(queryString, course_name):  # Added course_name as parameter
    index = load_index(course_name)  # Load the required index
    queryEngine = index.as_query_engine()
    return queryEngine.query(queryString)


@app.route("/file/upload", methods=["POST"])
def file_upload():
    try:
        if "file" not in request.files:
            return create_response(400, "File not found, Please upload a file", True, 'File not found, Please upload a file')
        
        file = request.files["file"]
        course_name = file.filename
        insert_file(file, course_name)
        
        return create_response(200, "File uploaded Successfully.", False, "File uploaded and Indexed")
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        print(e)  # For debugging purposes
        return create_response(400, str(e), True, "An error occurred during file upload")


@app.route("/query")
def query():
    try:
        query = request.args.get("search")
        course_name = request.args.get("index_name")

        if not course_name or not query:
            missing_param = "course name" if not course_name else "query"
            return create_response(404, "Error", True, f"{missing_param} not provided")
        
        index_path = os.path.join(DATA_DIR, course_name.replace(".pdf", ""))
        
        if not os.path.isdir(index_path):
            return create_response(404, "Error", True, "This course is not available")
        
        queryeng = queryFile(query, course_name)
        source = queryeng.source_nodes[0]
        result = queryeng.response

        return create_response(200, str(source), False, result)
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return create_response(500, "Error", True, {"error": str(e)})



@app.route('/chat', methods=['GET'])
def chat():
    index_name = request.args.get('index_name')

    if not index_name:
        return create_response(404, "Error", True, "Please provide a course name")

    
    return render_template('chat.html', index_name=index_name)




@app.route('/save_chat_history', methods=['POST'])
def save_chat_history():
    try:
        chat_data = request.json.get('chatData')
        index_name = request.json.get('index_name')
        email = request.json.get('email')
        print(email)
        save_to_json(index_name, email, chat_data)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/request_sign", methods=['GET', 'POST'])
def request_sign():
    if request.method == "POST":
        index_name = request.json.get('index_name')
        cn = index_name.replace(".pdf", "")
        email_content = request.json.get("email_content")
        email_body = request.json.get("email_body")
        clients = request.json.get("clients", [])
        sign_request = client.send_signature_request_embedded(
            test_mode=True,
            client_id=client_id,
            subject=email_body,
            message=email_content,
            signers=clients,
            files=[os.path.abspath(f"data/{cn}/{index_name}")]
        )
        # Initialize an empty list to hold the sign URLs
        # Save to JSON if necessary
        save_sign_urls(index_name, clients ,sign_request.signatures)

        return jsonify({
            "status": 200,
            "message": "Sign request sent successfully",
            "data": "",
        })
    else:
        return render_template("admin_page.html")


@app.route("/fetch_sign_url", methods=['GET'])
def fetch_sign_url():
    try:
        index_name = request.args.get('index_name')
        email =  request.args.get('email')
        cn = index_name.replace(".pdf", "")
        folder_path = os.path.join("data", cn)
        json_file_path = os.path.join(folder_path, "sign_data.json")

        with open(json_file_path, 'r') as f:
            data = json.load(f)

        if email in data:
            return create_response(200, "Data fetched successfully", False, data[email])
        
        else :
            return create_response(404, "Invalid email address", True, "Please insert a valid email address")


    except Exception as e:
        print(f"An error occurred: {e}")
        return create_response(500, "An error occurred", True, e)
    
if __name__ == '__main__':
    app.run(debug=True)
