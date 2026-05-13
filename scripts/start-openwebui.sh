export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
cd $HOME
export DATA_DIR=$HOME/.open-webui 
DATA_DIR=~/.open-webui HF_ENDPOINT=https://hf-mirror.com uvx --python 3.11 open-webui@latest serve