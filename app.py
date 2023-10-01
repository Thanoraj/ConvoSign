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


def save_to_json(index_name, sign_url_list, chat_history=None):
    cn = index_name.replace(".pdf", "")
    folder_path = os.path.join("data", cn)
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    json_file_path = os.path.join(folder_path, "sign_data.json")

    existing_data = {}
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as f:
            existing_data = json.load(f)

    existing_data.update({"index_name": index_name, "sign_url_list": sign_url_list})
    if chat_history:
        existing_data.update({"chat_history": chat_history})

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
    email = request.args.get('email')

    if not index_name or not email:
        return create_response(404, "Error", True, "Please provide both index_name and email")

    return render_template('chat.html', index_name=index_name, email=email)




@app.route('/save_chat_history', methods=['POST'])
def save_chat_history():
    try:
        chat_data = request.json.get('chatData')
        index_name = request.json.get('index_name')
        email = request.json.get('email')

        # sign_url = request.json.get('sign_url')  # If you have the sign_url, otherwise you can remove this
        save_to_json(index_name,  [{"email": email}], chat_data)
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

        # Create an empty list to hold email and sign_url pairs
        email_and_sign_url_list = []

        # Loop through each signature to associate it with an email
        for i, signature in enumerate(sign_request.signatures):
            signature_id = signature.signature_id
            sign_url = client.get_embedded_object(signature_id).sign_url
            email_address = clients[i]['email_address']
            email_and_sign_url_list.append({
                'email_address': email_address,
                'sign_url': sign_url
            })

        # Save to JSON (assuming save_to_json is defined elsewhere in your code)
        save_to_json(index_name, email_and_sign_url_list)

        return jsonify({
            "isError": False,
            "message": "Sign request sent successfully",
            "result": email_and_sign_url_list,
            "status-code": 200,
        }), 200
    else:
        return render_template("admin_page.html")


@app.route("/fetch_sign_url", methods=['GET'])
def fetch_sign_url():
    try:
        index_name = request.args.get('index_name')
        cn = index_name.replace(".pdf", "")
        folder_path = os.path.join("data", cn)
        json_file_path = os.path.join(folder_path, "sign_data.json")

        with open(json_file_path, 'r') as f:
            data = json.load(f)

        return jsonify({
            "isError": False,
            "message": "Data fetched successfully",
            "result": data,
            "status-code": 200,
        }), 200

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({
            "isError": True,
            "message": "An error occurred",
            "status-code": 500,
        }), 500
# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':       
#         json_data = request.json.get('json_data', {})
#         user_question = request.json.get('user_question', '')
#         result = run_conversation(user_question,json_data)
#         return jsonify(result) 
#     return render_template('index.html') ,200



if __name__ == '__main__':
    app.run(debug=True)
