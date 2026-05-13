"http://192.168.1.183:8002/tasks/d00c2406-60d1-4fb8-97f8-4d0bc7173847/result"

import requests
from pathlib import Path
resp=requests.get("http://192.168.1.183:8002/tasks/d00c2406-60d1-4fb8-97f8-4d0bc7173847/result")
resp_json=resp.json()

key=list(resp_json["results"].keys())[0]
result=resp_json["results"][key]

Path(f"data/{key}.md").write_text(result['md_content'])