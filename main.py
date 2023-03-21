from time import sleep

import uvicorn
from celery import Celery
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from manage_containers import run_code_with_tests, run_code_with_stdin

app = FastAPI()

celery_app = Celery(
    __name__,
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0"
)

NUMBER_OF_CONCURRENT_REQUESTS = 5


@app.post('/run_tests')
async def run_tests(tests: str, code: str) -> JSONResponse:
    """Проверяет код пользователя на тестах.
    Все тесты пройдены — возвращает 0, None.
    Тест не пройден — возвращает номер теста, None.
    Ошибка во время теста — возвращает номер теста, Traceback ошибки."""
    try:
        failed_test, error = enqueue_task(run_code_with_tests_task, tests, code)
    except Exception as e:
        return JSONResponse({'result': f'something went wrong', 'exception': f'{e}'})
    if failed_test == 0:
        return JSONResponse({'result': 'all good', 'traceback': None})
    elif error is not None:
        return JSONResponse({'result': f'error at {failed_test}', 'traceback': error})
    else:
        return JSONResponse({'result': f'failed at {failed_test}', 'traceback': None})


@app.post('/run_stdin')
def run_stdin(stdin: str, code: str) -> JSONResponse:
    """Запускает код пользователя внутри Docker контейнера на переданных
    входных данных.
    Возвращает stdout и Traceback ошибки.
    """
    try:
        stdout, stderr = enqueue_task(run_code_with_stdin_task, stdin, code)
    except Exception as e:
        return JSONResponse({'result': f'something went wrong', 'exception': f'{e}'})
    return JSONResponse({'stdout': stdout, 'stderr': stderr})


def enqueue_task(task, *args) -> str:
    """Запускает задачу celery, когда в очереди меньше
    NUMBER_OF_CONCURRENT_REQUESTS задач и возвращает результат.
    """
    i = celery_app.control.inspect()
    while len(i.active()) >= NUMBER_OF_CONCURRENT_REQUESTS:
        sleep(1)
    result = task.delay(*args)
    return result.get()


@celery_app.task
def run_code_with_tests_task(tests: str, code: str) -> tuple[int, str | None]:
    return run_code_with_tests(tests, code)


@celery_app.task
def run_code_with_stdin_task(stdin: str, code: str) -> tuple[str, str]:
    return run_code_with_stdin(stdin, code)


if __name__ == '__main__':
    uvicorn.run('main:app', port=8080, log_level='info')
