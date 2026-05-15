
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
sudo docker ps
sudo docker exec -it  busy_burnell /bin/bash
CUDA_VISIBLE_DEVICES=2 mineru-api --host 0.0.0.0 --port 8002
```
ctrl+p 结合 ctrl+q 不杀死的情况下退出



uv run -m pdf2md convert   20260515_005847 

python -m pdf2md get-result 20260515_005847

uv run -m pdf2md upload --knowledge-id 77e60d66-c754-4c39-9771-300f949eb75c 20260515_004918 --webui-url  http://192.168.1.183:8080                                                                                                                                                                                