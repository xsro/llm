# 启动mineru 服务 https://opendatalab.github.io/MinerU/quick_start/docker_deployment/#docker-description
docker run --gpus all \
  --shm-size 32g \
  -p 30000:30000 -p 7860:7860 -p 8000:8000 -p 8002:8002 \
  --ipc=host \
  -it mineru:latest \
  /bin/bash