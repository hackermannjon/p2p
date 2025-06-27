import json

def create_message(action, data):
    return json.dumps({
        "action": action,
        **data
    })

def parse_message(raw):
    return json.loads(raw)
