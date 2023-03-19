from time import sleep

import uvicorn
from celery import Celery
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from manage_containers import run_container

app = FastAPI()

celery_app = Celery(
    __name__,
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0"
)

NUMBER_OF_CONCURRENT_REQUESTS = 5


@app.post('/run')
async def run(tests: str, code: str) -> JSONResponse:
    """Проверяет код пользователя на тестах.
    Все тесты пройдены — возвращает 0, None.
    Тест не пройден — возвращает номер теста, None.
    Ошибка во время теста — возвращает номер теста, Traceback ошибки."""
    try:
        i = celery_app.control.inspect()
        while len(i.active()) >= NUMBER_OF_CONCURRENT_REQUESTS:
            sleep(1)
        result = run_container_task.delay(tests, code)
        failed_test, error = result.get()
    except Exception as e:
        return JSONResponse({'result': f'something went wrong', 'exception': f'{e}'})
    if failed_test == 0:
        return JSONResponse({'result': 'all good', 'traceback': None})
    elif error is not None:
        return JSONResponse({'result': f'error at {failed_test}', 'traceback': error})
    else:
        return JSONResponse({'result': f'failed at {failed_test}', 'traceback': None})


@celery_app.task
def run_container_task(tests: str, code: str) -> tuple[int, str | None]:
    return run_container(tests, code)


if __name__ == '__main__':
    uvicorn.run('main:app', port=8080, log_level='info')
