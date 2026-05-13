import requests
import time
from pathlib import Path

WEBUI_URL = 'http://127.0.0.1:8080'
TOKEN = 'sk-85ae27dd7ead4c6e958fbad54dcfb022'

def get_knowledge_file_page(knowledge_id,page):
    url=f"{WEBUI_URL}/api/v1/knowledge/{knowledge_id}/files?page={page}"
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json'
    }

    response = requests.get(
        url,
        headers=headers,
    )
    
    resp = response.json()

    return [item["filename"] for item in resp["items"]]

def get_knowledge_files(knowledge_id):
    page=1
    filenames_all=[]
    while True:
        page=page+1
        filenames=get_knowledge_file_page(knowledge_id,page)
        filenames_all.extend(filenames)
        if len(filenames)==0:
            break

    return filenames_all

def upload_and_add_to_knowledge(file_path, knowledge_id, timeout=300):
    """
    Upload a file and add it to a knowledge base.
    Properly waits for processing to complete before adding.
    """
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json'
    }
    
    # Step 1: Upload the file
    with open(file_path, 'rb') as f:
        response = requests.post(
            f'{WEBUI_URL}/api/v1/files/',
            headers=headers,
            files={'file': f}
        )
    
    if response.status_code != 200:
        raise Exception(f"Upload failed: {response.text}")
    
    file_data = response.json()
    file_id = file_data['id']
    print(f"File uploaded with ID: {file_id}")
    
    # Step 2: Wait for processing to complete
    print("Waiting for file processing...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status_response = requests.get(
            f'{WEBUI_URL}/api/v1/files/{file_id}/process/status',
            headers=headers
        )
        status_data = status_response.json()
        status = status_data.get('status')
        
        if status == 'completed':
            print("File processing completed!")
            break
        elif status == 'failed':
            raise Exception(f"Processing failed: {status_data.get('error')}")
        
        time.sleep(2)  # Poll every 2 seconds
    else:
        raise TimeoutError("File processing timed out")
    
    # Step 3: Add to knowledge base
    add_response = requests.post(
        f'{WEBUI_URL}/api/v1/knowledge/{knowledge_id}/file/add',
        headers={**headers, 'Content-Type': 'application/json'},
        json={'file_id': file_id}
    )
    
    if add_response.status_code != 200:
        raise Exception(f"Failed to add to knowledge: {add_response.text}")
    
    print(f"File successfully added to knowledge base!")
    return add_response.json()

# Usage
knowledge_id='e7b67d14-9b8c-4c09-aa90-1a334932da95'
files=get_knowledge_files(knowledge_id)
print("拉取了",len(files),"个已存储数据")


md_folder=Path("data/output_md/")
for f in md_folder.iterdir():
    if f.is_file():
        if f.name in files:
            print("skip",f)
            continue
        else:
            print("to upload", f.name)
            try:
                result = upload_and_add_to_knowledge(f.absolute().__str__(), knowledge_id)
            except Exception as e:
                print(e)


