import os
import flask
from flask import Flask, request, jsonify, request, Response, render_template
from llama_index import GPTVectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage, LLMPredictor, ServiceContext
from langchain import OpenAI
from flask_cors import CORS # Import the library
from creds import API_KEY, HELLOSIGN_API_KEY, client_id
import openai
from hellosign_sdk import HSClient
from flask import Flask, request, jsonify, render_template, redirect, url_for
# ... (your existing imports)
app = Flask(__name__,static_folder='data')
CORS(app)  # Enable CORS for the app

DATA_DIR = 'data'

os.environ['OPENAI_API_KEY']  = API_KEY
openai.api_key = API_KEY


client = HSClient(api_key=HELLOSIGN_API_KEY)



def insert_file(file, course_name):
    # filename = secure_filename(file.filename)
    file_dir = os.path.join(DATA_DIR, course_name)
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)  # Create a new directory for the file
    filename = file.filename
    
    filepath = os.path.join(file_dir, filename)
    file.save(filepath)
    document = SimpleDirectoryReader(file_dir).load_data()
    index = GPTVectorStoreIndex.from_documents(document)  # Store new index

    index.storage_context.persist(file_dir)

def load_index(course_name):
    DIRECTORY = "data"
    storage_path = os.path.join(DIRECTORY, course_name)
    # if os.path.exists(storage_path):
        # rebuild storage context
    storage_context = StorageContext.from_defaults(persist_dir=storage_path)
    # load index
    index = load_index_from_storage(storage_context)
    return index  # Load the index

def queryFile(queryString, course_name):  # Added course_name as parameter
    index = load_index(course_name)  # Load the required index
    queryEngine = index.as_query_engine()
    return queryEngine.query(queryString).response


@app.route("/file/upload", methods=["POST"])
def file_upload():
    try:
        if "file" not in request.files:
            # return "Please upload file", 400
            return jsonify({
                    "statusCode": 400,
                    "message": "Error",
                    "isError": True,
                    "result": 'Please upload a file'
                }), 400
        
    
        file = request.files["file"]
        course_name = file.filename

        # filename = file.filename
        insert_file(file, course_name)
        return jsonify({
            "statusCode": 200,
            "message": "File uploaded Successfully.",
            "isError": False,
            "result": "File uploaded and Indexed"
        }), 200
    
    except Exception as e:
        return jsonify({
            "statusCode": 500,  # Or appropriate error code
            "message": "Error",
            "isError": True,
            "result": {"error": str(e)}
        }), 500


@app.route("/query")
def query():
    try:
        query = request.args.get("search")
        course_name = request.args.get("index_name")

        if not course_name:
            # return "Please provide an index name", 400
            return jsonify({
                    "statusCode": 404,
                    "message": "Error",
                    "isError": True,
                    "result": "Please provide a course name"
                }), 404
        if not query:
            # return "Query Prompt not provided", 400
            return jsonify({
                "statusCode": 404,
                "message": "Error",
                "isError": True,
                "result": "Query Prompt not provided"
            }), 404
        
        index_path = os.path.join(DATA_DIR, course_name)
        if not os.path.isdir(index_path):
            # return jsonify({'error': 'This course is not available'}), 404
            return jsonify({
                "statusCode": 404,
                "message": "Error",
                "isError": True,
                "result": 'This course is not available'
            }), 404
        
        result = queryFile(query, course_name)
        
        # return flask.jsonify({"completion": result}), 200
        return jsonify({
            "statusCode": 200,
            "message": "Answer",
            "isError": False,
            "result": result
        }), 200
    
    except Exception as e:
        return jsonify({
            "statusCode": 500,  # Or appropriate error code
            "message": "Error",
            "isError": True,
            "result": {"error": str(e)}
        }), 500


@app.route('/chat', methods=['GET'])
def chat():
    index_name = request.args.get('index_name')

    if not index_name:
        return jsonify({
            "statusCode": 404,
            "message": "Error",
            "isError": True,
            "result": "Please provide a course name"
        }), 404

    return render_template('index.html', index_name=index_name)

@app.route('/sign', methods=['GET'])
def sign_document():
    index_name = request.args.get('index_name')
    if not index_name:
        return jsonify({
            "statusCode": 404,
            "message": "Error",
            "isError": True,
            "result": "Please provide a course name"
        }), 404

    # Create an embedded signature request
    sign_request = client.send_signature_request_embedded(
        test_mode=True,
        client_id= client_id,
        subject='My Subject',
        message='My Message',
        signers=[
            {'email_address': 'judesajith.aj@gmail.com', 'name': 'Jude Sajit'}
        ],
        files=[os.path.abspath(f"data/{index_name}/{index_name}")]
    )

    # Get the signature ID for the embedded request
    signature_id = sign_request.signatures[0].signature_id

    # Get the embedded signing URL
    sign_url = client.get_embedded_object(signature_id).sign_url

    return jsonify({"sign_url": sign_url})

if __name__ == '__main__':
    app.run(debug=True)
