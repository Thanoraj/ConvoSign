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
from json import dumps
import logging

from creds import API_KEY, HELLOSIGN_API_KEY, client_id
from llama_index.node_parser import SimpleNodeParser
from llama_index.node_parser.extractors import QuestionsAnsweredExtractor, MetadataExtractor
from llama_index.text_splitter import TokenTextSplitter

# Initialize logging
logging.basicConfig(level=logging.INFO)


app = Flask(__name__)

CORS(app)  # Enable CORS for the app


DATA_DIR = 'data'

os.environ['OPENAI_API_KEY']  = API_KEY
openai.api_key = API_KEY


client = HSClient(api_key=HELLOSIGN_API_KEY)


# Assume this function is called every time a message is sent or received
# def cache_message(email, message):
#     if email in session:
#         session[email].append(message)
#     else:
#         session[email] = [message]


def create_qa_metadata_extractor(llm):
    DEFAULT_QUESTION_GEN_TMPL = """\
Here is the context:
{context_str}

Given the contextual information from a document that should be signed by a signing party, \
generate {num_questions} questions with less than 20 tokens that the document signing parties can have regarding this context \
specific answers to which are unlikely to be found elsewhere.

Higher-level summaries of surrounding context may be provided \
as well. Try using these summaries to generate better questions \
that signers need to ask, that this context can answer.

"""
    return MetadataExtractor(
        

        extractors=[
            QuestionsAnsweredExtractor(questions=1, llm=llm,prompt_template=DEFAULT_QUESTION_GEN_TMPL),
        ],
        in_place=False,
    )

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

def save_chat(index_name, email, chat_history=None):
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
    
    if chat_history:
        existing_data[email].update({"chat_history": chat_history})

    with open(json_file_path, 'w') as f:
        json.dump(existing_data, f)



def save_to_json(index_name, key ,value):
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
    
   
    existing_data[key] = value

    with open(json_file_path, 'w') as f:
        json.dump(existing_data, f)


def load_json (index_name):
    cn = index_name.replace(".pdf", "")
    folder_path = os.path.join("data", cn)

    if not os.path.exists(folder_path):
       return {}

    
    json_file_path = os.path.join(folder_path, "sign_data.json")

    existing_data = {}
    
    try:
        with open(json_file_path, 'r') as f:
            existing_data = json.load(f)

    except Exception as e:
        print(e)


    return existing_data

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
    queryEngine = index.as_query_engine( include_text=True,
    retriever_mode="keyword")
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
        source = queryeng.source_nodes
        print(source)
        list_of_dict_nodes = [{"node": str(node.node), "score": node.score,"page_label": node.node.metadata} for node in source]

# Convert list of dictionaries to JSON string
        json_string = dumps(list_of_dict_nodes)
        result = queryeng.response
        

        return create_response(200, str(json_string), False, result)
    
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
        save_chat(index_name, email, chat_data)
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
            # use_text_tags=True,
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
        print(json_file_path)

        with open(json_file_path, 'r') as f:
            data = json.load(f)
        print(data)

        if email in data:
            return create_response(200, "Data fetched successfully", False, data[email])
        
        else :
            return create_response(404, "Invalid email address", True, "Please insert a valid email address")


    except Exception as e:
        print(f"An error occurred: {e}")
        return create_response(500, "An error occurred", True, e)
    




# from llama_index import SimpleDirectoryReader

@app.route('/extract_qa', methods=['POST'])
def extract_qa():
    try:
        index_name = request.json.get('index_name')
        if not index_name:
            return jsonify({"status": 400, "message": "Index name not provided"}), 400

        # Construct the path to the document
        cn = index_name.replace(".pdf", "")
        folder_path = os.path.join("data", cn)

        # Read the document content using SimpleDirectoryReader
        reader = SimpleDirectoryReader(folder_path)

        # from llama_index.schema import Document
        # doc = Document(text=text)

        # text_splitter = TokenTextSplitter(separator=" ", chunk_size=512, chunk_overlap=128)

        data = load_json(index_name)
        print(data)
        if "questionslist" not in data:
            print("in")
            document = reader.load_data()
            
            # Initialize LLM and metadata extractor
            llm = OpenAI(temperature=0.1, model="text-davinci-003", max_tokens=512)
            metadata_extractor = create_qa_metadata_extractor(llm)
            node_parser = SimpleNodeParser.from_defaults()
            orig_nodes = node_parser.get_nodes_from_documents(document)
            print(len(orig_nodes))
            # Extract questions and answers
            nodes = metadata_extractor.process_nodes(orig_nodes[:5])
            list_of_dict_nodes = [{ "question": node.metadata["questions_this_excerpt_can_answer"]} for node in nodes]
            save_to_json(index_name,"questionslist", list_of_dict_nodes )
        else:
            list_of_dict_nodes = data["questionslist"]

        json_string = {"questionslist": list_of_dict_nodes}
        # result = queryeng.response

        
        # qa_list = [ndata]

        return jsonify({"status": 200, "message": "Questions and answers extracted successfully", "data": json_string}), 200

    except Exception as e:
        return jsonify({"status": 500, "message": str(e)}), 500

    
if __name__ == '__main__':
    app.run(debug=True)
