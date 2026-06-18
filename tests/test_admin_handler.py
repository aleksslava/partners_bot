import pytest

from handlers.admin_handler import (
    BROADCAST_CONFIGS,
    BROADCAST_KIND_TRAINING,
    normalize_telegram_id,
    parse_spam_range,
    spam_text,
)
from lexicon.lexicon_ru import spam_message_2


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('1-10', (1, 10)),
        (' 2 - 5 ', (2, 5)),
        ('7-7', (7, 7)),
    ],
)
def test_parse_spam_range_valid(text: str, expected: tuple[int, int]) -> None:
    assert parse_spam_range(text) == expected


@pytest.mark.parametrize(
    'text',
    [
        '',
        '0-1',
        '10-1',
        '1',
        '1:10',
        'one-ten',
    ],
)
def test_parse_spam_range_invalid(text: str) -> None:
    assert parse_spam_range(text) is None


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (123456, 123456),
        (123456.0, 123456),
        ('123456', 123456),
        (' 123456 ', 123456),
    ],
)
def test_normalize_telegram_id_valid(value: object, expected: int) -> None:
    assert normalize_telegram_id(value) == expected


@pytest.mark.parametrize('value', ['abc', '123.4', 123.4, ''])
def test_normalize_telegram_id_invalid(value: object) -> None:
    with pytest.raises(ValueError, match='Некорректный telegram_id'):
        normalize_telegram_id(value)


def test_spam_text_replaces_interview_name() -> None:
    text = spam_text('Иван')

    assert 'Здравствуйте, Иван!' in text
    assert '[Имя]' not in text


def test_spam_text_keeps_training_message_without_name_mask() -> None:
    config = BROADCAST_CONFIGS[BROADCAST_KIND_TRAINING]

    assert spam_text(name='Иван', message=config.message) == spam_message_2
