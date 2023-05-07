## Installation
1. Install gVisor as a Docker runtime following the [user guide](https://gvisor.dev/docs/user_guide/install/)
2. Install Python requirements
```shell
pip install -r requirements.txt
```
## Start
```shell
docker run -p 6379:6379 --name practice-redis -d redis
celery -A main.celery_app worker --loglevel=info
python main.py
```
