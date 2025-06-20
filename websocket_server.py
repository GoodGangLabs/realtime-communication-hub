from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from connection_manager import ConnectionManager
import json
import os
from pathlib import Path
from jsonschema import Draft7Validator, RefResolver, ValidationError

from constants.message_types import MESSAGE_TYPE
from constants.client_ids import CLIENT_ID

app = FastAPI()
manager = ConnectionManager()

# ────── JSON Schema 로딩 ──────
PROJECT_ROOT = Path(__file__).parent
SCHEMA_BASE_PATH = PROJECT_ROOT / "websocket-schema" / "schemas"
MESSAGE_SCHEMA_PATH = SCHEMA_BASE_PATH / "message.schema.json"
SHARED_SCHEMA_PATH = SCHEMA_BASE_PATH / "shared"
PAYLOAD_SCHEMA_DIR = SCHEMA_BASE_PATH / "payloads"

# message.schema.json 로딩
with open(MESSAGE_SCHEMA_PATH, encoding='utf-8') as f:
    message_schema = json.load(f)

resolver = RefResolver(
    base_uri=f"file://{SCHEMA_BASE_PATH}/",
    referrer=message_schema
)

message_validator = Draft7Validator(schema=message_schema, resolver=resolver)

def validate_message(message_data):
    # 메시지가 스키마에 맞는지 검증
    try:
        # 1. 기본 메시지 구조 검증
        message_validator.validate(message_data)
        
        # 2. Payload 스키마 검증
        message_type = message_data.get("type")
        payload_schema_path = PAYLOAD_SCHEMA_DIR / f"{message_type}.json"
        
        if payload_schema_path.exists():
            with open(payload_schema_path, encoding='utf-8') as f:
                payload_schema = json.load(f)
            payload = message_data.get("payload", {})
            Draft7Validator(payload_schema).validate(payload)
            
        return True, None
        
    except ValidationError as e:
        error_msg = f"Schema validation failed: {e.message}"
        return False, error_msg

@app.websocket("/{group}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, group: str, client_id: str):
    await manager.connect(websocket, group, client_id)
    try:
        while True:
            raw_msg = await websocket.receive_text()
            print(f"RAW MESSAGE: {raw_msg}")
            
            try:
                message = json.loads(raw_msg)
            except json.JSONDecodeError:
                print(f"JSON DECODE ERROR: {raw_msg}")
                continue
            
            # 스키마 검증
            is_valid, error_msg = validate_message(message)
            if not is_valid:
                print(f"SCHEMA VALIDATION FAILED: {error_msg}")
                print(f"Message type: {message.get('type')}")
                print(f"Message content: {json.dumps(message, indent=2, ensure_ascii=False)}")
                continue

            # 메시지 로깅
            print(f"\n MESSAGE RECEIVED")
            print(f"From: {client_id} (Group: {group})")
            print(f"Type: {message.get('type')}")
            print("Content:")
            print(json.dumps(message, indent=2, ensure_ascii=False))
            print("-" * 80)

            # 필수 필드 추출
            type_ = message.get("type")
            sender = message.get("sender", {})
            targets = message.get("targets", [])
            payload = message.get("payload", {})

            # 스푸핑 방지 (보안 위험 → 연결 끊기)
            if (sender.get("group") != group or 
                sender.get("clientId") != client_id):
                print(f"🚨 [SECURITY] Sender spoofing detected: sender={sender}, expected={{group={group}, clientId={client_id}}}")
                await websocket.close(code=1008, reason="Sender spoofing detected")
                return

            # 메시지 중계
            target_websockets = manager.get_targets(targets)
            for target_ws in target_websockets:
                if target_ws != websocket:  # 자기 자신에게는 전송하지 않음
                    try:
                        await target_ws.send_text(raw_msg)
                        print(f"MESSAGE SENT to target")
                    except RuntimeError as e:
                        # 연결이 끊어진 경우
                        print(f"ERROR - Connection closed: {e}")
                        manager.disconnect(group, client_id)
                    except Exception as e:
                        # 기타 예외 발생 시
                        print(f"ERROR - Unexpected error: {e}")
                        manager.disconnect(group, client_id)
                else:
                    print(f"MESSAGE SENT to self")

    except WebSocketDisconnect:
        print(f"DISCONNECTED - Client: {client_id}, Group: {group}")
        manager.disconnect(group, client_id)