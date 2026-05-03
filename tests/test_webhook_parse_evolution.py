"""Evolution / Baileys webhook payload parsing."""

from app.api.webhook import parse_evolution_messages_payload


def test_nested_message_key_shape_from_docs():
    """WEBHOOK.md: key lives under data.message, not data."""
    payload = {
        "event": "MESSAGES_UPSERT",
        "session": "inika",
        "data": {
            "message": {
                "key": {
                    "remoteJid": "15551234567@s.whatsapp.net",
                    "fromMe": False,
                    "id": "abc123",
                },
                "message": {
                    "conversation": "Hello, I need help with my reservation",
                },
                "pushName": "John Doe",
            }
        },
    }
    out = parse_evolution_messages_payload(payload)
    assert out is not None
    from_n, text, key = out
    assert "15551234567" in from_n or from_n == "15551234567"
    assert "reservation" in text
    assert key.get("id") == "abc123"


def test_flat_baileys_shape():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "447700900123@s.whatsapp.net",
                "fromMe": False,
                "id": "mid",
            },
            "message": {"conversation": "Hi there"},
        },
    }
    out = parse_evolution_messages_payload(payload)
    assert out is not None
    assert out[1] == "Hi there"
    assert "447700900123" in out[0]


def test_skips_from_me():
    payload = {
        "data": {
            "key": {"remoteJid": "x@s.whatsapp.net", "fromMe": True},
            "message": {"conversation": "echo"},
        }
    }
    assert parse_evolution_messages_payload(payload) is None


def test_batch_messages_array():
    payload = {
        "data": {
            "messages": [
                {
                    "key": {
                        "remoteJid": "15550001111@s.whatsapp.net",
                        "fromMe": False,
                    },
                    "message": {"conversation": "First line"},
                }
            ]
        }
    }
    out = parse_evolution_messages_payload(payload)
    assert out is not None
    assert out[1] == "First line"
