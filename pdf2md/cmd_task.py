from .config import __proj
from datetime import datetime
import json
from pathlib import Path

def run_create_task(init:str,args):
    print(__proj)
        
    # 生成格式：20251225_143025（年月日_时分秒）
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_dir = __proj / "data" / "tasks" / task_id

    if not task_dir.exists():
        task_dir.mkdir(parents=True,exist_ok=True)

    task_json=task_dir/"pdfs.json"
    if init=="empty":
        tasks={
            "pdfs":[
                {
                "path":None,
                "name":""
            }]
        }
    elif init=="folder":
        pdfs0=list(Path(args.folder).rglob("*.pdf"))
        pdfs=[{"path":p.absolute().__str__(),"name":p.stem} for p in pdfs0]
        tasks={"pdfs":pdfs}
    task_json.write_text(json.dumps(tasks,indent=2,ensure_ascii=False, ))

    print("created task",task_dir)

        
