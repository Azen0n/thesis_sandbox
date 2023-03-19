## Installation
```shell
pip install -r requirements.txt
```
## Start
```shell
docker run -p 6379:6379 --name practice-redis -d redis
celery -A main.celery_app worker --loglevel=info
python main.py
```