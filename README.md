Telegram bot that sends messages with specified delays.

Here is an example of config:

```python
MESSAGES = {
    None: {
        'next_msg_delay': 0,
        'next_msg_id': 1,
    },
    1: {
        'msg_media_type': MediaType.PHOTO,
        'msg_media': 'room.jpg',
        'msg_text': 'Super message 1',
        'next_msg_delay': 1,
        'next_msg_id': 8,
    },
    8: {
        'msg_media_type': MediaType.VIDEO,
        'msg_media': 'stars.mkv',
        'msg_text': 'Super message 1',
        'next_msg_delay': 2,
        'next_msg_id': 3,
    },
    3: {
        'msg_text': 'Super message 4',
        'next_msg_delay': 10,
        'next_msg_id': 4,
    },
    4: {
        'msg_text': 'Super message 5',
        'next_msg_delay': 10,
        'next_msg_id': 5,
    },
    5: {
        'msg_text': 'Super message 6',
        'next_msg_time': DAY_START,
        'next_msg_id': 6,
    },
    6: {
        'msg_text': 'Super message 7',
        'next_msg_time': DAY_START,
        'next_msg_id': 7,
    },
    7: {
        'msg_text': 'Super message 8',
        'next_msg_time': DAY_START,
        'next_msg_id': None,
    },
}
```
