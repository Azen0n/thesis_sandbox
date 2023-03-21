import enum
import re

import docker
from docker.errors import BuildError, APIError, ContainerError, ImageNotFound
from docker.models.containers import Container

client = docker.from_env()


def run_code_with_tests(tests: str, code: str) -> tuple[int, str | None]:
    """Запускает код пользователя внутри Docker контейнера и проверяет его
    на тестах.
    Все тесты пройдены — возвращает 0, None.
    Тест не пройден — возвращает номер теста, None.
    Ошибка во время теста — возвращает номер теста, Traceback ошибки.
    """
    logs = run_container(f'/bin/sh run.sh "{tests}" "{code}"')
    if not logs:
        raise Exception('Неизвестная ошибка во время проверки кода.')
    failed_test, error = parse_tests_logs(logs)
    return failed_test, error


def run_code_with_stdin(stdin: str, code: str) -> tuple[str, str]:
    """Запускает код пользователя внутри Docker контейнера на переданных
    входных данных.
    Возвращает stdout и Traceback ошибки.
    """
    logs = run_container(f'/bin/sh run_stdin.sh "{stdin}" "{code}"')
    if not logs:
        raise Exception('Неизвестная ошибка во время проверки кода.')
    try:
        stdout, stderr = parse_stdout_or_stderr_logs(logs)
    except ValueError:
        raise
    return stdout, stderr


def run_container(cmd: str) -> str:
    """Запускает контейнер, выполняет команду и возвращает логи."""
    image_id = build_image(dockerfile='./')
    container = create_container(image=image_id)
    result = container.exec_run(cmd=cmd)
    container.stop()
    client.images.get(image_id).remove(force=True)
    logs = result.output.decode('utf-8')
    return logs


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


def parse_tests_logs(logs: str) -> tuple[int, str | None]:
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


def parse_stdout_or_stderr_logs(logs: str) -> tuple[str, str]:
    """Возвращает stdout и stderr (Traceback ошибки)."""
    pattern = r'(?:\[OUTPUT\]\n(?P<output>[\s\S]+)?)|(?:\[ERROR\]\n(?P<error>[\s\S]+)?)'
    for match in re.finditer(pattern, logs):
        if match.group('error') is not None:
            return '', match.group('error')
        if match.group('output') is not None:
            return match.group('output'), ''
    raise ValueError('Неизвестный формат stdout.')
