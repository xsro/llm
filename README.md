# 本地运行大模型让它并学习控制理论

- `ollama.com` 大模型
- `open webui` 交互前后端
- [marker](https://github.com/datalab-to/marker) pdf2md

## 安装记录

```sh
# 

```

```sh
# 运行open webui
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
cd $HOME
export DATA_DIR=$HOME/.open-webui 
DATA_DIR=~/.open-webui HF_ENDPOINT=https://hf-mirror.com uvx --python 3.11 open-webui@latest serve
```


## trouble shooting

upload a file to the knowledge [ 400: Embedding dimension ] 

related to [#10153](https://github.com/open-webui/open-webui/issues/10153)