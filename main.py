import json
from time import sleep
from urllib.parse import unquote

import uvicorn
from celery import Celery
from fastapi import FastAPI, Depends
from fastapi.openapi.models import APIKey
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import get_api_key
from manage_containers import run_code_with_tests, run_code_with_stdin

app = FastAPI()

celery_app = Celery(
    __name__,
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0"
)

NUMBER_OF_CONCURRENT_REQUESTS = 5


class TestCode(BaseModel):
    tests: str
    code: str

    def __init__(self, **data):
        data['tests'] = unquote(data['tests'])
        data['tests'] = json.dumps(data['tests']).strip('"')
        data['code'] = unquote(data['code'])
        data['code'] = json.dumps(data['code']).strip('"')
        super().__init__(**data)


class RunCode(BaseModel):
    stdin: str
    code: str

    def __init__(self, **data):
        data['stdin'] = unquote(data['stdin'])
        data['stdin'] = json.dumps(data['stdin']).strip('"')
        data['code'] = unquote(data['code'])
        data['code'] = json.dumps(data['code']).strip('"')
        super().__init__(**data)


@app.post('/run_tests')
async def run_tests(test_code: TestCode, api_key: APIKey = Depends(get_api_key)) -> JSONResponse:
    """Проверяет код пользователя внутри Docker контейнера на тестах
    и возвращает ResultResponse.
    """
    result_response = enqueue_task(
        run_code_with_tests_task,
        test_code.tests,
        test_code.code
    )
    return JSONResponse(result_response)


@app.post('/run_stdin')
def run_stdin(run_code: RunCode, api_key: APIKey = Depends(get_api_key)) -> JSONResponse:
    """Запускает код пользователя внутри Docker контейнера на переданных
    входных данных и возвращает ResultResponse.
    """
    result_response = enqueue_task(
        run_code_with_stdin_task,
        run_code.stdin,
        run_code.code
    )
    return JSONResponse(result_response)


def enqueue_task(task, *args) -> dict:
    """Запускает задачу celery, когда в очереди меньше
    NUMBER_OF_CONCURRENT_REQUESTS задач и возвращает результат.
    """
    i = celery_app.control.inspect()
    while len(i.active()) >= NUMBER_OF_CONCURRENT_REQUESTS:
        sleep(1)
    result = task.delay(*args)
    return result.get()


@celery_app.task
def run_code_with_tests_task(tests: str, code: str) -> dict:
    result_response = run_code_with_tests(tests, code)
    return result_response.to_dict()


@celery_app.task
def run_code_with_stdin_task(stdin: str, code: str) -> dict:
    result_response = run_code_with_stdin(stdin, code)
    return result_response.to_dict()


if __name__ == '__main__':
    uvicorn.run('main:app', port=8080, log_level='info')
