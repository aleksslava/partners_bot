import asyncio
import math
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_admin.auth import client_key, get_csrf_token, is_authenticated, valid_csrf
from web_admin.service import (
    ALLOWED_MEDIA,
    MAX_MEDIA_SIZE,
    UploadValidationError,
    message_limit,
    parse_recipients,
    render_message,
)

ADMIN_PREFIX = '/tg_partners/admin'
MOSCOW_TZ = ZoneInfo('Europe/Moscow')
TEMPLATES_DIR = Path(__file__).resolve().parent / 'templates'
templates = Jinja2Templates(directory=TEMPLATES_DIR)
router = APIRouter(prefix=ADMIN_PREFIX)

STATUS_LABELS = {
    'draft': 'Черновик',
    'scheduled': 'Запланирована',
    'running': 'Выполняется',
    'completed': 'Завершена',
    'completed_with_errors': 'Завершена с ошибками',
    'cancelled': 'Отменена',
    'pending': 'Ожидает',
    'sending': 'Отправляется',
    'success': 'Успешно',
    'error': 'Ошибка',
    'skipped': 'Пропуск',
}


def format_moscow(value: str | None) -> str:
    if not value:
        return '—'
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')


templates.env.filters['moscow'] = format_moscow
templates.env.globals['status_labels'] = STATUS_LABELS
templates.env.globals['admin_prefix'] = ADMIN_PREFIX


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse(f'{ADMIN_PREFIX}/login', status_code=status.HTTP_303_SEE_OTHER)


def _base_context(request: Request, **values: Any) -> dict[str, Any]:
    return {
        'request': request,
        'csrf_token': get_csrf_token(request),
        **values,
    }


def _require_admin(request: Request) -> RedirectResponse | None:
    if not is_authenticated(request):
        return _redirect_to_login()
    return None


def _require_csrf(request: Request, csrf_token: str) -> None:
    if not valid_csrf(request, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid_csrf')


def _parse_schedule(value: str) -> datetime:
    if not value.strip():
        return datetime.now(timezone.utc)
    try:
        local_value = datetime.fromisoformat(value)
    except ValueError as error:
        raise UploadValidationError('Некорректные дата и время запуска.') from error
    if local_value.tzinfo is None:
        local_value = local_value.replace(tzinfo=MOSCOW_TZ)
    return max(local_value.astimezone(timezone.utc), datetime.now(timezone.utc))


def _validate_button(button_text: str, button_url: str) -> tuple[str | None, str | None]:
    text = button_text.strip()
    url = button_url.strip()
    if bool(text) != bool(url):
        raise UploadValidationError('Для кнопки нужно указать и текст, и ссылку.')
    if len(text) > 64:
        raise UploadValidationError('Текст кнопки должен быть не длиннее 64 символов.')
    parsed_url = urlparse(url)
    if url and (parsed_url.scheme != 'https' or not parsed_url.netloc):
        raise UploadValidationError('Укажите корректную HTTPS-ссылку кнопки.')
    return text or None, url or None


@router.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(ADMIN_PREFIX, status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name='login.html',
        context={'error': None},
    )


@router.post('/login', response_class=HTMLResponse)
async def login(request: Request, password: Annotated[str, Form()]):
    key = client_key(request)
    limiter = request.app.state.admin_rate_limiter
    if limiter.is_blocked(key):
        return templates.TemplateResponse(
            request=request,
            name='login.html',
            context={'error': 'Слишком много попыток. Повторите вход через 15 минут.'},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    expected_password = request.app.state.admin_config.password
    if not secrets.compare_digest(password, expected_password):
        limiter.record_failure(key)
        return templates.TemplateResponse(
            request=request,
            name='login.html',
            context={'error': 'Неверный пароль.'},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    limiter.clear(key)
    request.session.clear()
    request.session['admin_authenticated'] = True
    get_csrf_token(request)
    return RedirectResponse(ADMIN_PREFIX, status_code=status.HTTP_303_SEE_OTHER)


@router.post('/logout')
async def logout(request: Request, csrf_token: Annotated[str, Form()]):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    _require_csrf(request, csrf_token)
    request.session.clear()
    return _redirect_to_login()


@router.get('', response_class=HTMLResponse)
async def dashboard(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    broadcasts = request.app.state.admin_service.storage.list_broadcasts()
    summary = {
        'scheduled': sum(item['status'] == 'scheduled' for item in broadcasts),
        'running': sum(item['status'] == 'running' for item in broadcasts),
        'success': sum(item['success_count'] for item in broadcasts),
        'errors': sum(item['error_count'] for item in broadcasts),
    }
    return templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context=_base_context(request, broadcasts=broadcasts, summary=summary),
    )


@router.get('/new', response_class=HTMLResponse)
async def new_broadcast(request: Request):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request,
        name='new.html',
        context=_base_context(
            request,
            error=None,
            values={
                'send_telegram': True,
                'send_max': request.app.state.admin_config.max_enabled,
            },
            max_enabled=request.app.state.admin_config.max_enabled,
        ),
    )


@router.post('/preview', response_class=HTMLResponse)
async def preview_broadcast(
    request: Request,
    csrf_token: Annotated[str, Form()],
    message: Annotated[str, Form()],
    send_telegram: Annotated[str | None, Form()] = None,
    send_max: Annotated[str | None, Form()] = None,
    scheduled_at: Annotated[str, Form()] = '',
    button_text: Annotated[str, Form()] = '',
    button_url: Annotated[str, Form()] = '',
    recipients_file: UploadFile = File(...),
    media_file: UploadFile | None = File(default=None),
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    _require_csrf(request, csrf_token)
    values = {
        'message': message,
        'send_telegram': bool(send_telegram),
        'send_max': bool(send_max),
        'scheduled_at': scheduled_at,
        'button_text': button_text,
        'button_url': button_url,
    }
    media_path: Path | None = None
    try:
        targets = set()
        if send_telegram:
            targets.add('telegram')
        if send_max:
            targets.add('max')
        if not targets:
            raise UploadValidationError('Выберите хотя бы одного бота.')
        if 'max' in targets and not request.app.state.admin_config.max_enabled:
            raise UploadValidationError('Интеграция MAX не настроена на сервере.')
        message = message.strip()
        if not message:
            raise UploadValidationError('Введите текст сообщения.')
        source_filename = Path(recipients_file.filename or '').name
        if Path(source_filename).suffix.casefold() != '.xlsx':
            raise UploadValidationError('Загрузите список получателей в формате .xlsx.')
        button_text_value, button_url_value = _validate_button(button_text, button_url)
        schedule_value = _parse_schedule(scheduled_at)

        media_kind = None
        media_original_name = None
        media_content = b''
        if media_file is not None and media_file.filename:
            media_original_name = Path(media_file.filename).name
            media_suffix = Path(media_original_name).suffix.casefold()
            media_kind = ALLOWED_MEDIA.get(media_suffix)
            if media_kind is None:
                raise UploadValidationError('Допустимы изображения JPG/PNG и видео MP4.')
            media_content = await media_file.read(MAX_MEDIA_SIZE + 1)
            if len(media_content) > MAX_MEDIA_SIZE:
                raise UploadValidationError('Медиафайл должен быть не больше 20 МБ.')
            if not media_content:
                raise UploadValidationError('Медиафайл пуст.')

        text_limit = message_limit(targets, bool(media_kind))
        if len(message) > text_limit:
            raise UploadValidationError(
                f'Сообщение должно быть не длиннее {text_limit} символов.'
            )

        excel_content = await recipients_file.read(10 * 1024 * 1024 + 1)
        recipients, validation_stats = await asyncio.to_thread(
            parse_recipients,
            excel_content,
            message,
            targets=targets,
            message_limit_value=text_limit,
        )

        service = request.app.state.admin_service
        if media_kind and media_original_name:
            media_path = service.media_dir / f'{uuid.uuid4().hex}{Path(media_original_name).suffix.casefold()}'
            await asyncio.to_thread(media_path.write_bytes, media_content)

        broadcast_id = service.storage.create_draft(
            message=message,
            source_filename=source_filename,
            media_path=str(media_path) if media_path else None,
            media_kind=media_kind,
            media_original_name=media_original_name,
            button_text=button_text_value,
            button_url=button_url_value,
            scheduled_at=schedule_value,
            recipients=recipients,
            targets=targets,
            validation_stats=validation_stats,
        )
        broadcast = service.storage.get_broadcast(broadcast_id)
        sample = [
            item
            for item in recipients
            if any(delivery['status'] == 'pending' for delivery in item['deliveries'])
        ][:5]
        preview_message = render_message(message, sample[0].get('name', '')) if sample else message
        return templates.TemplateResponse(
            request=request,
            name='preview.html',
            context=_base_context(
                request,
                broadcast=broadcast,
                recipients=sample,
                validation_stats=validation_stats,
                preview_message=preview_message,
            ),
        )
    except UploadValidationError as error:
        if media_path:
            media_path.unlink(missing_ok=True)
        return templates.TemplateResponse(
            request=request,
            name='new.html',
            context=_base_context(
                request,
                error=str(error),
                values=values,
                max_enabled=request.app.state.admin_config.max_enabled,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@router.post('/broadcasts/{broadcast_id}/confirm')
async def confirm_broadcast(
    request: Request,
    broadcast_id: int,
    csrf_token: Annotated[str, Form()],
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    _require_csrf(request, csrf_token)
    service = request.app.state.admin_service
    if not service.storage.confirm_draft(broadcast_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='broadcast_not_draft')
    service.wake()
    return RedirectResponse(
        f'{ADMIN_PREFIX}/broadcasts/{broadcast_id}',
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post('/broadcasts/{broadcast_id}/discard')
async def discard_draft(
    request: Request,
    broadcast_id: int,
    csrf_token: Annotated[str, Form()],
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    _require_csrf(request, csrf_token)
    service = request.app.state.admin_service
    media_path = service.storage.delete_draft(broadcast_id)
    service.delete_media(media_path)
    return RedirectResponse(f'{ADMIN_PREFIX}/new', status_code=status.HTTP_303_SEE_OTHER)


@router.post('/broadcasts/{broadcast_id}/cancel')
async def cancel_broadcast(
    request: Request,
    broadcast_id: int,
    csrf_token: Annotated[str, Form()],
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    _require_csrf(request, csrf_token)
    service = request.app.state.admin_service
    cancelled, media_path = service.storage.cancel(broadcast_id)
    if not cancelled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='broadcast_not_cancellable')
    service.delete_media(media_path)
    return RedirectResponse(
        f'{ADMIN_PREFIX}/broadcasts/{broadcast_id}',
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get('/broadcasts/{broadcast_id}', response_class=HTMLResponse)
async def broadcast_detail(
    request: Request,
    broadcast_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
):
    redirect = _require_admin(request)
    if redirect:
        return redirect
    service = request.app.state.admin_service
    broadcast = service.storage.get_broadcast(broadcast_id)
    if broadcast is None or broadcast['status'] == 'draft':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    page_size = 100
    pages = max(1, math.ceil(broadcast['total_count'] / page_size))
    page = min(page, pages)
    recipients = service.storage.get_recipients(
        broadcast_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return templates.TemplateResponse(
        request=request,
        name='detail.html',
        context=_base_context(
            request,
            broadcast=broadcast,
            recipients=recipients,
            page=page,
            pages=pages,
        ),
    )


@router.get('/broadcasts/{broadcast_id}/status')
async def broadcast_status(request: Request, broadcast_id: int):
    if not is_authenticated(request):
        return JSONResponse({'detail': 'unauthorized'}, status_code=status.HTTP_401_UNAUTHORIZED)
    broadcast = request.app.state.admin_service.storage.get_broadcast(broadcast_id)
    if broadcast is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    processed = broadcast['success_count'] + broadcast['error_count']
    valid_count = broadcast['valid_count'] or 0
    progress = round(processed / valid_count * 100) if valid_count else 100
    return {
        'status': broadcast['status'],
        'status_label': STATUS_LABELS.get(broadcast['status'], broadcast['status']),
        'success_count': broadcast['success_count'],
        'error_count': broadcast['error_count'],
        'skipped_count': broadcast['skipped_count'],
        'processed_count': processed,
        'valid_count': valid_count,
        'progress': min(progress, 100),
        'platforms': broadcast['platform_stats'],
    }
