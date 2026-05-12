# https://opendatalab.github.io/MinerU/quick_start/docker_deployment/

wget https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/docker/global/Dockerfile

sudo docker build -t mineru:latest -f Dockerfile .