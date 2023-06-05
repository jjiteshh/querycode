
import inspect
from quart import Quart, request, jsonify
import quart_cors
from chromadb.config import Settings
import chromadb
import quart
import os
from importlib import import_module
from PyPDF2 import PdfReader
import datetime


app = quart_cors.cors(quart.Quart(__name__), allow_origin="*")


def tokenize_into_chunks(text, chunk_size):
    tokens = text.split()
    chunks = [tokens[i:i+chunk_size] for i in range(0, len(tokens), chunk_size)]
    chunks = [' '.join(chunk) for chunk in chunks]
    return chunks


def save_code_to_collection(collection):
    for filename in os.listdir('.'):
        if filename.endswith(('.txt', '.json', '.yaml', '.py', '.pdf')):
            if filename.endswith('.pdf'):
                with open(filename, 'rb') as file:
                    pdf_reader = PdfReader(file)
                    all_code = ""
                    for page in pdf_reader.pages:
                        all_code += page.extract_text()
            else:
                with open(filename, 'r') as file:
                    all_code = file.read()
            
            token_chunks = tokenize_into_chunks(all_code, 200)
            for i, chunk in enumerate(token_chunks):
                metadata = {'filename': filename, 'chunk_number': i}
                id = f'{filename}_chunk_{i}'
                collection.add(documents=[chunk], metadatas=[metadata], ids=[id])



def add_line_to_file(filename, line_number, line_content):

    ('prinitng trying to add line... ')
    with open(filename, 'r') as file:
        lines = file.readlines()

    # Insert the new line
    lines.insert(line_number - 1, line_content + '\n')

    with open(filename, 'w') as file:
        file.writelines(lines)



def get_function_source(module, function_name):
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and name == function_name:
            try:
                source_lines, start_line_number = inspect.getsourcelines(obj)
                end_line_number = start_line_number + len(source_lines) - 1
                source_code = ''.join(source_lines)
                return source_code, start_line_number, end_line_number
            except (TypeError, OSError):
                return "Source not available for this function.", None, None
    return "The specified function does not exist in this module.", None, None


def get_python_tree(module):
    result = {}
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            result[name] = [m[0] for m in inspect.getmembers(obj) if inspect.isfunction(m[1]) and m[1].__module__ == module.__name__]
        elif inspect.isfunction(obj) and obj.__module__ == module.__name__:
            result[name] = []
    return result


def get_class_method_source(module, class_name, method_name):
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and name == class_name:
            for m_name, m_obj in inspect.getmembers(obj):
                if inspect.isfunction(m_obj) and m_name == method_name:
                    try:
                        source_lines, start_line_number = inspect.getsourcelines(m_obj)
                        end_line_number = start_line_number + len(source_lines) - 1
                        source_code = ''.join(source_lines)
                        return source_code, start_line_number, end_line_number
                    except (TypeError, OSError):
                        return "Source not available for this method.", None, None
    return "The specified class or method does not exist in this module.", None, None



def get_global_code(module):
     # Read the entire module as a text file
    with open(module.__file__, 'r') as file:
        all_code = file.read()

    # Subtract the source code of each class and function
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) or inspect.isfunction(obj):
            try:
                source_lines, start_line_number = inspect.getsourcelines(obj)
                end_line_number = start_line_number + len(source_lines) - 1
                source_code = ''.join(source_lines)
                all_code = all_code.replace(source_code, '')
            except (TypeError, OSError):
                pass

    return all_code, start_line_number, end_line_number

@app.route('/save_summary', methods=['POST'])
async def save_summary():
    data = await request.get_json()
    summary = data.get('summary')
    metadata = data.get('metadata')
    id = data.get('id')  # Get the ID from the request data

    longterm_memory_collection.add(
        documents=[summary],
        metadatas=[{'metadata':metadata}],
        ids=[id]
    )

    return jsonify({'message': 'Summary saved successfully'}), 200


@app.route('/execute_query', methods=['POST'])
async def execute_query():
    data = await request.get_json()
    query = data.get('query')
    n_results = data.get('n_results', 2)  # use 2 as default if not provided
    results = short_term_memory_collection.query(query_texts=[query], n_results=1)
    return jsonify(results), 200

@app.route('/query_memory', methods=['POST'])
async def query_memory():
    data = await request.get_json()
    query = data.get('query')
    n_results = data.get('n_results', 2)  # use 2 as default if not provided
    results = longterm_memory_collection.query(query_texts=[query], n_results=n_results)
    return jsonify(results), 200



@app.route('/add_line_to_file/<filename>/<int:line_number>', methods=['POST'])
async def add_line_to_file_endpoint(filename, line_number):
    request_data = await request.get_json()
    line_content = request_data.get('line_content', '')
    print(line_content)
    print('ADDING LINE CURRENTLY DISABLED')
    #add_line_to_file(filename, line_number, line_content)
    #return jsonify({'message': 'Line added successfully'}), 200
    return jsonify({'message': 'Line addtion is currently disabled'}), 200



@app.route('/get_file_contents/<filename>', methods=['GET'])
async def get_file_contents(filename):
    try:
        with open(filename, 'r') as file:
            data = file.read()
        return jsonify({'file_contents': data})
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    

@app.route('/get_function_source/<module_name>/<function_name>', methods=['GET'])
async def get_function_source_endpoint(module_name, function_name):
    module = import_module(module_name)
    result = get_function_source(module, function_name)
    return jsonify({'source_code': result}), 200


@app.route('/get_classes_and_functions/<module_name>', methods=['GET'])
async def get_classes_and_functions_endpoint(module_name):
    module = import_module(module_name)
    result = get_python_tree(module)
    return jsonify(result), 200


@app.route('/get_class_method_source/<module_name>/<class_name>/<method_name>', methods=['GET'])
async def get_class_method_source_endpoint(module_name, class_name, method_name):
    module = import_module(module_name)
    source_code, start_line_number, end_line_number = get_class_method_source(module, class_name, method_name)
    return jsonify({
        'source_code': source_code,
        'start_line_number': start_line_number,
        'end_line_number': end_line_number
    }), 200

@app.route('/get_global_code/<module_name>', methods=['GET'])
async def get_global_code_endpoint(module_name):
    module = import_module(module_name)
    result = get_global_code(module)
    return jsonify({'global_code': result}), 200


@app.route('/getcwd', methods=['GET'])
async def get_cwd_endpoint():
    cwd = os.getcwd()
    return jsonify({'current_directory': cwd}), 200


@app.route('/getfiles', methods=['GET'])
async def get_files_endpoint():
    cwd = os.getcwd()
    files = os.listdir(cwd)
    return jsonify({'files': files}), 200


@app.get("/logo.png")
async def plugin_logo():
    filename = 'logo.png'
    return await quart.send_file(filename, mimetype='image/png')



@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    host = request.headers['Host']
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")
    

@app.get("/openapi.yaml")
async def openapi_spec():
    host = request.headers['Host']
    with open("openapi.yaml") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/yaml")



if __name__ == "__main__":
    import panel as pn 

    

    client = chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory="/Users/jiteshh/tomato/.chromadb"
    ))
    # Create a new collection every time the server starts
    collection_name = "short_term_memory_collection_" + str(datetime.datetime.now().timestamp())
    short_term_memory_collection = client.create_collection(name=collection_name)
    save_code_to_collection(short_term_memory_collection)


    memory_name = "LongTermMemory"
    # Check if the memory collection already exists
    existing_collections = client.list_collections()
    memory_exists = any(collection.name == memory_name for collection in existing_collections)

    # Create a new memory collection if it does not exist
    if not memory_exists:
        longterm_memory_collection = client.create_collection(name=memory_name)
        print("New memory collection created:", longterm_memory_collection.name)
    else:
        print("Memory collection already exists:", memory_name)
        longterm_memory_collection = client.get_collection(name=memory_name)


    #collection = client.get_collection(name="my_collection7")
    #print(collection.get())
    app.run(debug=True, host="0.0.0.0", port=4400)
