from enum import Enum
import re
from dataclasses import dataclass
from re import Match

import docker
from docker.errors import BuildError, APIError, ContainerError, ImageNotFound
from docker.models.containers import Container

client = docker.from_env()


class ResultCode(Enum):
    OK = 'OK'
    CE = 'Compilation error'
    WA = 'Wrong answer'
    TL = 'Time-limit exceeded'
    ML = 'Memory limit exceeded'


@dataclass
class ResultResponse:
    """Результат запуска кода на входных данных или тестах. Неиспользованные
    поля остаются пустыми.

    :cvar stdout: вывод в консоль во время запуска кода,
    :cvar stderr: Traceback ошибки во время запуска кода,
    :cvar code: код запуска,
    :cvar test: номер проваленного теста,
    :cvar error: ошибка при запуске контейнера.
    """
    stdout: str = ''
    stderr: str = ''
    code: ResultCode = ''
    test: int = ''
    error: str = ''

    def to_dict(self):
        code = self.code.value if type(self.code) == ResultCode else ''
        return {
            'stdout': self.stdout,
            'stderr': self.stderr,
            'code': code,
            'test': self.test,
            'error': self.error
        }


def run_code_with_tests(tests: str, code: str) -> ResultResponse:
    """Запускает код пользователя внутри Docker контейнера и проверяет его
    на тестах.
    """
    logs = run_container(f'/bin/sh run.sh "{tests}" "{code}"')
    if not logs:
        return ResultResponse(error='Неизвестная ошибка во время проверки кода')
    failed_test, stderr = parse_tests_logs(logs)
    if failed_test == 0:
        return ResultResponse(code=ResultCode.OK)
    if stderr == 'timeout':
        return ResultResponse(stderr=stderr, code=ResultCode.TL, test=failed_test)
    if stderr:
        return ResultResponse(stderr=stderr, code=ResultCode.CE, test=failed_test)
    return ResultResponse(code=ResultCode.WA, test=failed_test)


def run_code_with_stdin(stdin: str, code: str) -> ResultResponse:
    """Запускает код пользователя внутри Docker контейнера на переданных
    входных данных.
    """
    logs = run_container(f'/bin/sh run_stdin.sh "{stdin}" "{code}"')
    if not logs:
        return ResultResponse(error='Неизвестная ошибка во время запуска кода')
    try:
        stdout, stderr = parse_stdout_or_stderr_logs(logs)
    except ValueError as e:
        return ResultResponse(error=f'{e}')
    if stderr == 'timeout':
        return ResultResponse(stderr=stderr, code=ResultCode.TL)
    elif stderr:
        return ResultResponse(stderr=stderr, code=ResultCode.CE)
    return ResultResponse(stdout=stdout, code=ResultCode.OK)


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


class Status(Enum):
    PASSED = 'PASSED'
    FAILED = 'FAILED'
    ERROR = 'ERROR'
    TIMEOUT = 'TIMEOUT'


def parse_tests_logs(logs: str) -> tuple[int, str]:
    """Все тесты пройдены (PASSED) — возвращает 0 и пустую строку.
    Тест не пройден (FAILED) — возвращает номер теста и пустую строку.
    Ошибка во время теста (ERROR) — возвращает номер теста и Traceback ошибки.
    Превышено время (TIMEOUT) — возвращает номер теста и строку 'timeout'.
    """
    pattern = r'\[(?P<status>.+?)\].+\n(?P<traceback>Traceback[\s\S]+)?'
    for i, test in enumerate(re.finditer(pattern, logs), start=1):
        if test.group('status') == Status.FAILED.value:
            return i, ''
        if test.group('status') == Status.ERROR.value:
            if is_timeout(test, logs):
                return i, 'timeout'
            return i, test.group('traceback')
    return 0, ''


def is_timeout(test: Match, logs: str) -> bool:
    """Возвращает True, если тест превысил лимит по времени."""
    error_start_pos = test.regs[1][0]
    if error_start_pos - 12 >= 0:
        return logs[error_start_pos - 12:error_start_pos - 2] == 'Terminated'
    return False


def parse_stdout_or_stderr_logs(logs: str) -> tuple[str, str]:
    """Возвращает stdout и stderr (Traceback ошибки)."""
    pattern = (r'(?:\[OUTPUT\]\n(?P<output>[\s\S]+)?)'
               r'|(?:\[ERROR\]\n(?P<error>[\s\S]+)?)'
               r'|(?:Terminated\n(?P<timeout>[\s\S]+)?)')
    for match in re.finditer(pattern, logs):
        if match.group('error') is not None:
            return '', match.group('error')
        if match.group('output') is not None:
            return match.group('output'), ''
        if match.group('timeout') is not None:
            return '', 'timeout'
    raise ValueError('Неизвестный формат stdout')
