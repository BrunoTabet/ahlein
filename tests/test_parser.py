from app.webhook.parser import parse_webhook


def _payload(text: str, phone_number_id: str = "100000000000001") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"profile": {"name": "Jane"}, "wa_id": "9715000"}],
                            "messages": [
                                {
                                    "from": "9715000",
                                    "id": "wamid.1",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def test_parses_text_message():
    msgs = parse_webhook(_payload("hello"))
    assert len(msgs) == 1
    assert msgs[0].phone_number_id == "100000000000001"
    assert msgs[0].from_number == "9715000"
    assert msgs[0].text == "hello"
    assert msgs[0].profile_name == "Jane"


def test_ignores_non_text_messages():
    payload = _payload("hi")
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    assert parse_webhook(payload) == []


def test_handles_status_only_payloads():
    # Delivery/read status callbacks carry no `messages` — must not error.
    payload = {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "x"}}}]}]}
    assert parse_webhook(payload) == []
