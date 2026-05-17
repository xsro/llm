from pathlib import Path
import shutil

folder=Path("data/md_out")
folder.mkdir(exist_ok=True)
for f in Path("data/output").glob("**/*.md"):
    print(f)
    shutil.copy(f,folder.joinpath(f.name))
    