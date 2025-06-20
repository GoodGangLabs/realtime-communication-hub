from fastapi import WebSocket
from typing import Dict, Optional, List, Tuple, TypedDict

class TargetInfo(TypedDict):
    group: str
    clientId: str

class ConnectionManager:
    def __init__(self):
        # (group, client_id) -> websocket
        self.connections: Dict[Tuple[str, str], WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, group: str, client_id: str):
        await websocket.accept()
        self.connections[(group, client_id)] = websocket
        print(f"[CONNECTED] group={group}, client_id={client_id}")
    
    def disconnect(self, group: str, client_id: str):
        key = (group, client_id)
        if key in self.connections:
            del self.connections[key]
            print(f"[DISCONNECTED] group={group}, client_id={client_id}")
    
    def get(self, group: str, client_id: str) -> Optional[WebSocket]:
        return self.connections.get((group, client_id))
    
    def get_targets(self, targets: List[TargetInfo]) -> List[WebSocket]:
        """
        targets 배열에 있는 각 타겟에 대해 해당하는 웹소켓 연결을 반환합니다.
        각 타겟은 group, clientId를 포함하는 딕셔너리여야 합니다.
        """
        result = []
        for target in targets:
            group = target["group"]
            client_id = target["clientId"]
            
            if client_id == "all":
                # 해당 group의 모든 클라이언트에게 전송
                for (g, cid), ws in self.connections.items():
                    if g == group:
                        result.append(ws)
            else:
                # 특정 클라이언트에게만 전송
                ws = self.get(group, client_id)
                if ws:
                    result.append(ws)
        return result
