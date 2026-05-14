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
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:cuda
```

docker logs -f open-webui

docker exec -it open-webui /bin/bash

### pdf2md 文件识别软件

```bash
# 启动mineru 服务 https://opendatalab.github.io/MinerU/quick_start/docker_deployment/#docker-description
docker run --gpus all \
  --shm-size 32g \
  -p 30000:30000 -p 7860:7860 -p 8000:8000 -p 8002:8002 \
  --ipc=host \
  -it mineru:latest \
  /bin/bash
```

```bash
# 在上面的命令启动的终端里面输入 https://opendatalab.github.io/MinerU/usage/quick_usage/#quick-usage-via-command-line
CUDA_VISIBLE_DEVICES=1 mineru-api --host 0.0.0.0 --port 8000

# 另外启动一个服务 专门给open webui 用
sudo docker exec -it  sweet_yalow /bin/bash
CUDA_VISIBLE_DEVICES=2 mineru-api --host 0.0.0.0 --port 8002
```
ctrl+p 结合 ctrl+q 不杀死的情况下退出



## trouble shooting

upload a file to the knowledge [ 400: Embedding dimension ] 

related to [#10153](https://github.com/open-webui/open-webui/issues/10153)