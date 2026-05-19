# 本地运行大模型让它并学习控制理论

- `ollama.com` 大模型
- `open webui` 交互前后端
- [marker](https://github.com/datalab-to/marker) pdf2md

## 安装记录

### open webui 页面


```
docker run -d -p 8080:8080 \
  --gpus all \
  -e OLLAMA_BASE_URL=http://172.17.0.1:11434 \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/ \
  -e ENV=dev \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:cuda
```

docker logs -f open-webui

docker exec -it open-webui /bin/bash


## trouble shooting

upload a file to the knowledge [ 400: Embedding dimension ] 

related to [#10153](https://github.com/open-webui/open-webui/issues/10153)