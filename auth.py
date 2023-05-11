from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name='access_token', auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Проверка ключа API из заголовка запроса."""
    if api_key == 'some_key':
        return api_key
    raise HTTPException(status_code=403)
