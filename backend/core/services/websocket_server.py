"""
WebSocket Server Integration for Suna AI with Playwright Browser Automation

This module connects the SunaBridge (Electron) with the browser automation system.
It handles WebSocket connections, command routing, and real-time screen streaming.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logging.warning("websockets not installed")

try:
    from core.services.browser_automation import (
        BrowserAutomation,
        handle_browser_command,
        get_browser_manager
    )
    BROWSER_AUTOMATION_AVAILABLE = True
except ImportError:
    BROWSER_AUTOMATION_AVAILABLE = False
    logging.warning("Browser automation module not available")

logger = logging.getLogger(__name__)


class CommandType(str, Enum):
    """WebSocket command types"""
    HANDSHAKE = "handshake"
    COMMAND = "command"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_APPROVED = "permission_approved"
    PERMISSION_DENIED = "permission_denied"
    STATUS_CHANGED = "status_changed"
    BROWSER_ACTION = "browser_action"
    SCREENSHOT = "screenshot"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class SunaSession:
    """Represents an active Suna AI session"""
    session_id: str
    user_id: str
    created_at: datetime
    websocket: Optional[WebSocketServerProtocol] = None
    browser_id: Optional[str] = None
    status: str = "active"
    last_heartbeat: Optional[datetime] = None
    execution_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "browser_id": self.browser_id,
            "status": self.status,
            "execution_count": self.execution_count
        }


@dataclass
class BrowserCommand:
    """Represents a browser automation command"""
    command_id: str
    session_id: str
    action: str
    parameters: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SunaWebSocketServer:
    """
    WebSocket server for Suna AI backend
    Handles bidirectional communication with Electron/Pulse
    """
    
    def __init__(self, host: str = "localhost", port: int = 7070):
        self.host = host
        self.port = port
        self.sessions: Dict[str, SunaSession] = {}
        self.pending_permissions: Dict[str, Dict[str, Any]] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.session_lock = asyncio.Lock()
        
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets package required: pip install websockets")
    
    def register_handler(self, command_type: str, handler: Callable) -> None:
        """Register custom command handler"""
        self.message_handlers[command_type] = handler
        logger.info(f"Registered handler for {command_type}")
    
    async def handle_connection(
        self,
        websocket: WebSocketServerProtocol,
        path: str
    ) -> None:
        """
        Handle new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        session_id = None
        user_id = None
        
        try:
            logger.info(f"New connection from {websocket.remote_address}")
            
            # Wait for handshake
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get("type") != CommandType.HANDSHAKE.value:
                await self._send_error(websocket, "Expected handshake first")
                return
            
            session_id = data.get("sessionId")
            user_id = data.get("userId")
            
            if not session_id or not user_id:
                await self._send_error(websocket, "Missing sessionId or userId")
                return
            
            # Create session
            async with self.session_lock:
                session = SunaSession(
                    session_id=session_id,
                    user_id=user_id,
                    created_at=datetime.now(),
                    websocket=websocket,
                    browser_id=f"browser-{session_id}"
                )
                self.sessions[session_id] = session
            
            logger.info(f"Session created: {session_id} for user {user_id}")
            
            # Send handshake acknowledgment
            await self._send_message(websocket, {
                "type": CommandType.HANDSHAKE.value,
                "status": "acknowledged",
                "sessionId": session_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Handle messages
            await self._message_loop(websocket, session)
            
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for session {session_id}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            # Cleanup
            if session_id:
                async with self.session_lock:
                    if session_id in self.sessions:
                        session = self.sessions[session_id]
                        if session.browser_id:
                            manager = await get_browser_manager()
                            await manager.close_browser(session.browser_id)
                        del self.sessions[session_id]
                logger.info(f"Session cleaned up: {session_id}")
    
    async def _message_loop(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession
    ) -> None:
        """
        Main message processing loop
        
        Args:
            websocket: WebSocket connection
            session: Active session
        """
        heartbeat_task = asyncio.create_task(self._heartbeat(websocket, session))
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(websocket, session, data)
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await self._send_error(websocket, str(e))
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
    
    async def _process_message(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession,
        data: Dict[str, Any]
    ) -> None:
        """
        Process incoming message
        
        Args:
            websocket: WebSocket connection
            session: Active session
            data: Message data
        """
        msg_type = data.get("type")
        
        if msg_type == CommandType.COMMAND.value:
            await self._handle_command(websocket, session, data)
        
        elif msg_type == CommandType.PERMISSION_APPROVED.value:
            await self._handle_permission_approved(websocket, session, data)
        
        elif msg_type == CommandType.PERMISSION_DENIED.value:
            await self._handle_permission_denied(websocket, session, data)
        
        elif msg_type == CommandType.BROWSER_ACTION.value:
            await self._handle_browser_action(websocket, session, data)
        
        elif msg_type == CommandType.HEARTBEAT.value:
            session.last_heartbeat = datetime.now()
            await self._send_message(websocket, {
                "type": CommandType.HEARTBEAT.value,
                "status": "pong",
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            # Try custom handler
            if msg_type in self.message_handlers:
                handler = self.message_handlers[msg_type]
                result = await handler(data, session)
                await self._send_message(websocket, result)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
    
    async def _handle_command(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession,
        data: Dict[str, Any]
    ) -> None:
        """
        Handle command execution request
        
        Args:
            websocket: WebSocket connection
            session: Active session
            data: Command data
        """
        command_id = data.get("commandId", str(uuid.uuid4()))
        command_text = data.get("text", "")
        priority = data.get("priority", "normal")
        
        logger.info(f"Command received: {command_text} (priority: {priority})")
        
        # Request permission if needed
        permission_id = str(uuid.uuid4())
        self.pending_permissions[permission_id] = {
            "command_id": command_id,
            "session_id": session.session_id,
            "command_text": command_text,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send permission request to frontend
        await self._send_message(websocket, {
            "type": CommandType.PERMISSION_REQUEST.value,
            "permissionId": permission_id,
            "action": "execute_command",
            "commandId": command_id,
            "commandText": command_text,
            "priority": priority,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _handle_browser_action(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession,
        data: Dict[str, Any]
    ) -> None:
        """
        Handle browser automation action
        
        Args:
            websocket: WebSocket connection
            session: Active session
            data: Browser action data
        """
        try:
            if not BROWSER_AUTOMATION_AVAILABLE:
                await self._send_error(websocket, "Browser automation not available")
                return
            
            # Execute browser action
            data["browser_id"] = session.browser_id
            result = await handle_browser_command(data)
            
            # Send result back
            await self._send_message(websocket, {
                "type": CommandType.BROWSER_ACTION.value,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            session.execution_count += 1
            
        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            await self._send_error(websocket, f"Browser action failed: {e}")
    
    async def _handle_permission_approved(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession,
        data: Dict[str, Any]
    ) -> None:
        """Handle permission approval"""
        permission_id = data.get("permissionId")
        
        if permission_id not in self.pending_permissions:
            await self._send_error(websocket, "Invalid permission ID")
            return
        
        perm_data = self.pending_permissions[permission_id]
        command_id = perm_data["command_id"]
        command_text = perm_data["command_text"]
        
        del self.pending_permissions[permission_id]
        
        logger.info(f"Permission approved for command: {command_text}")
        
        # Execute command (placeholder)
        await self._send_message(websocket, {
            "type": CommandType.STATUS_CHANGED.value,
            "status": "executing",
            "commandId": command_id,
            "message": f"Executing: {command_text}",
            "timestamp": datetime.now().isoformat()
        })
        
        # Simulate execution
        await asyncio.sleep(0.5)
        
        # Send completion
        await self._send_message(websocket, {
            "type": CommandType.STATUS_CHANGED.value,
            "status": "completed",
            "commandId": command_id,
            "result": f"Command executed: {command_text}",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _handle_permission_denied(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession,
        data: Dict[str, Any]
    ) -> None:
        """Handle permission denial"""
        permission_id = data.get("permissionId")
        
        if permission_id in self.pending_permissions:
            del self.pending_permissions[permission_id]
        
        logger.info(f"Permission denied for ID: {permission_id}")
        
        await self._send_message(websocket, {
            "type": CommandType.STATUS_CHANGED.value,
            "status": "denied",
            "permissionId": permission_id,
            "message": "Command permission denied by user",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _heartbeat(
        self,
        websocket: WebSocketServerProtocol,
        session: SunaSession
    ) -> None:
        """Send periodic heartbeat"""
        try:
            while True:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                await self._send_message(websocket, {
                    "type": CommandType.HEARTBEAT.value,
                    "status": "ping",
                    "sessionId": session.session_id,
                    "timestamp": datetime.now().isoformat()
                })
        except asyncio.CancelledError:
            pass
    
    async def _send_message(
        self,
        websocket: WebSocketServerProtocol,
        data: Dict[str, Any]
    ) -> None:
        """Send message to client"""
        try:
            message = json.dumps(data)
            await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed while sending message")
    
    async def _send_error(
        self,
        websocket: WebSocketServerProtocol,
        error_message: str
    ) -> None:
        """Send error message to client"""
        await self._send_message(websocket, {
            "type": CommandType.ERROR.value,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def start(self) -> None:
        """Start WebSocket server"""
        try:
            logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")
            
            async with websockets.serve(
                self.handle_connection,
                self.host,
                self.port
            ):
                logger.info(f"✅ WebSocket server running on ws://{self.host}:{self.port}")
                await asyncio.Future()  # Run forever
        
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise


# Standalone entry point
async def main():
    """Start Suna WebSocket server"""
    server = SunaWebSocketServer()
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
