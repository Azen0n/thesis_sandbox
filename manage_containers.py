import enum
import re

import docker
from docker.errors import BuildError, APIError, ContainerError, ImageNotFound
from docker.models.containers import Container

client = docker.from_env()


def run_container(tests: str, code: str) -> tuple[int, str | None]:
    """Запускает код пользователя внутри Docker контейнера и проверяет его
    на тестах.
    Все тесты пройдены — возвращает 0, None.
    Тест не пройден — возвращает номер теста, None.
    Ошибка во время теста — возвращает номер теста, Traceback ошибки.
    """
    image_id = build_image(dockerfile='./')
    container = create_container(image=image_id)
    result = container.exec_run(cmd=f'/bin/sh run.sh "{tests}" "{code}"')
    container.stop()
    client.images.get(image_id).remove(force=True)
    logs = result.output.decode('utf-8')
    if not logs:
        raise Exception('Неизвестная ошибка во время проверки кода.')
    failed_test, error = parse_logs(logs)
    return failed_test, error


def write_files(tests: str, code: str):
    """Записывает тесты и код пользователя в соответствующие файлы."""
    try:
        tests = re.sub(r'\\n', '\n', tests)
        code = re.sub(r'\\n', '\n', code)
        with open('data/tests.txt', 'w') as f:
            f.write(tests)
        with open('data/code.py', 'w') as f:
            f.write(code)
    except OSError as e:
        raise Exception(f'{e}')


def build_image(dockerfile: str) -> str:
    """Создает образ python-sandbox."""
    try:
        image = client.images.build(path=dockerfile, rm=True)[0]
        image_id = re.sub(r'(sha256:)', '', image.short_id)
    except (BuildError, APIError) as e:
        raise Exception(f'{e}')
    return image_id


def create_container(image: str) -> Container:
    """Создает и запускает контейнер."""
    try:
        container = client.containers.run(
            image=image,
            remove=True,
            runtime='runsc',
            mem_limit='128m',
            network_disabled=True,
            tty=True,
            detach=True
        )
    except (ContainerError, ImageNotFound, APIError) as e:
        raise Exception(f'{e}')
    return container


class Status(enum.Enum):
    PASSED = 'PASSED'
    FAILED = 'FAILED'
    ERROR = 'ERROR'


def parse_logs(logs: str) -> tuple[int, str | None]:
    """Все тесты пройдены (PASSED) — возвращает 0, None.
    Тест не пройден (FAILED) — возвращает номер теста, None.
    Ошибка во время теста (ERROR) — возвращает номер теста, Traceback ошибки.
    """
    pattern = r'\[(?P<status>.+?)\].+\n(?P<traceback>Traceback[\s\S]+)?'
    for i, test in enumerate(re.finditer(pattern, logs), start=1):
        if test.group('status') == Status.FAILED.value:
            return i, None
        if test.group('status') == Status.ERROR.value:
            return i, test.group('traceback')
    return 0, None


def main():
    tests = r'2,5,\n5.0\n1,9,\n4.5\n3,10,\n15.0\n'
    code = r'x = int(input())\ny = int(input())\nprint(x * y / 2)\n'
    failed_test, error = run_container(tests, code)
    print(failed_test, error)


if __name__ == '__main__':
    main()
