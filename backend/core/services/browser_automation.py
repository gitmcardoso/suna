"""
Browser Automation Module for Suna AI
Handles VM browser automation, screen capture, and action execution via Playwright
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright not installed. Install with: pip install playwright>=1.40.0")

logger = logging.getLogger(__name__)


class BrowserAutomationError(Exception):
    """Custom exception for browser automation errors"""
    pass


class BrowserAutomation:
    """
    Manages browser automation for VM control
    
    Features:
    - Navigate to URLs
    - Take screenshots
    - Click elements
    - Type text
    - Execute JavaScript
    - Extract page content
    - Handle navigation waits
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        """
        Initialize browser automation
        
        Args:
            headless: Run browser in headless mode (no UI)
            timeout_ms: Timeout for page operations in milliseconds
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright is not installed")
        
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_initialized = False

    async def initialize(self) -> None:
        """Initialize browser and launch"""
        try:
            if self.is_initialized:
                logger.warning("Browser already initialized")
                return
            
            self.playwright = await async_playwright().start()
            
            # Launch Chromium browser
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Create context and page
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
            # Set default timeout
            self.page.set_default_timeout(self.timeout_ms)
            
            self.is_initialized = True
            logger.info("Browser initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise BrowserAutomationError(f"Initialization failed: {e}")

    async def close(self) -> None:
        """Close browser and cleanup"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            self.is_initialized = False
            logger.info("Browser closed")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def navigate(self, url: str, wait_until: str = "networkidle") -> Dict[str, Any]:
        """
        Navigate to URL
        
        Args:
            url: Target URL
            wait_until: 'load', 'domcontentloaded', 'networkidle', or 'commit'
        
        Returns:
            Navigation result with status and details
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            # Validate URL
            if not url.startswith(('http://', 'https://', 'file://')):
                url = f"https://{url}"
            
            start_time = datetime.now()
            response = await self.page.goto(url, wait_until=wait_until)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "url": url,
                "status_code": response.status if response else None,
                "elapsed_seconds": elapsed,
                "title": await self.page.title(),
                "timestamp": start_time.isoformat()
            }
            
            logger.info(f"Navigated to {url} in {elapsed}s")
            return result
            
        except Exception as e:
            logger.error(f"Navigation failed to {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def take_screenshot(self, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Take screenshot of current page
        
        Args:
            filename: Optional filename to save screenshot
        
        Returns:
            Screenshot data with base64 encoded image
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            # Take screenshot
            screenshot_bytes = await self.page.screenshot()
            
            # Encode as base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Optionally save to file
            file_path = None
            if filename:
                file_path = Path(filename)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(screenshot_bytes)
            
            result = {
                "success": True,
                "image_base64": screenshot_b64,
                "size_bytes": len(screenshot_bytes),
                "file_path": str(file_path) if file_path else None,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Screenshot taken ({len(screenshot_bytes)} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def click(self, selector: str) -> Dict[str, Any]:
        """
        Click element by CSS selector
        
        Args:
            selector: CSS selector for element
        
        Returns:
            Click result
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            await self.page.click(selector)
            
            result = {
                "success": True,
                "selector": selector,
                "action": "click",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Clicked element: {selector}")
            return result
            
        except Exception as e:
            logger.error(f"Click failed on {selector}: {e}")
            return {
                "success": False,
                "selector": selector,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def type_text(self, selector: str, text: str, delay_ms: int = 50) -> Dict[str, Any]:
        """
        Type text into element
        
        Args:
            selector: CSS selector for input element
            text: Text to type
            delay_ms: Delay between key presses (ms)
        
        Returns:
            Type result
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            await self.page.fill(selector, text)
            
            result = {
                "success": True,
                "selector": selector,
                "action": "type",
                "text_length": len(text),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Typed {len(text)} characters into {selector}")
            return result
            
        except Exception as e:
            logger.error(f"Type failed on {selector}: {e}")
            return {
                "success": False,
                "selector": selector,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def execute_javascript(self, script: str, *args) -> Dict[str, Any]:
        """
        Execute JavaScript in page context
        
        Args:
            script: JavaScript code to execute
            args: Arguments to pass to script
        
        Returns:
            Execution result with return value
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            result_value = await self.page.evaluate(script, args)
            
            result = {
                "success": True,
                "action": "execute_javascript",
                "return_value": result_value,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"JavaScript executed, returned: {type(result_value).__name__}")
            return result
            
        except Exception as e:
            logger.error(f"JavaScript execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def get_page_content(self) -> Dict[str, Any]:
        """
        Get page HTML content and extracted text
        
        Returns:
            Page content and metadata
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            html = await self.page.content()
            text = await self.page.evaluate("document.body.innerText")
            url = self.page.url
            title = await self.page.title()
            
            result = {
                "success": True,
                "url": url,
                "title": title,
                "html_size": len(html),
                "text_preview": text[:500],  # First 500 chars
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Page content retrieved ({len(html)} bytes HTML)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def press_key(self, key: str) -> Dict[str, Any]:
        """
        Press keyboard key
        
        Args:
            key: Key name (e.g., 'Enter', 'Tab', 'Escape', 'ArrowDown')
        
        Returns:
            Key press result
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            await self.page.press("body", key)
            
            result = {
                "success": True,
                "action": "press_key",
                "key": key,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Key pressed: {key}")
            return result
            
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Wait for element to appear
        
        Args:
            selector: CSS selector
            timeout_ms: Custom timeout (uses default if None)
        
        Returns:
            Wait result
        """
        if not self.is_initialized or not self.page:
            raise BrowserAutomationError("Browser not initialized")
        
        try:
            timeout = timeout_ms or self.timeout_ms
            await self.page.wait_for_selector(selector, timeout=timeout)
            
            result = {
                "success": True,
                "selector": selector,
                "action": "wait_for_selector",
                "timeout_ms": timeout,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Element appeared: {selector}")
            return result
            
        except Exception as e:
            logger.error(f"Wait for selector failed: {e}")
            return {
                "success": False,
                "selector": selector,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class BrowserAutomationManager:
    """
    Manages browser automation lifecycle and connections
    Thread-safe wrapper for multiple browser instances
    """
    
    def __init__(self):
        self.browsers: Dict[str, BrowserAutomation] = {}
        self.lock = asyncio.Lock()
    
    async def create_browser(self, browser_id: str, headless: bool = True) -> BrowserAutomation:
        """Create and initialize a new browser instance"""
        async with self.lock:
            if browser_id in self.browsers:
                logger.warning(f"Browser {browser_id} already exists")
                return self.browsers[browser_id]
            
            browser = BrowserAutomation(headless=headless)
            await browser.initialize()
            self.browsers[browser_id] = browser
            
            logger.info(f"Created browser instance: {browser_id}")
            return browser
    
    async def get_browser(self, browser_id: str) -> Optional[BrowserAutomation]:
        """Get existing browser instance"""
        return self.browsers.get(browser_id)
    
    async def close_browser(self, browser_id: str) -> None:
        """Close and remove browser instance"""
        async with self.lock:
            if browser_id in self.browsers:
                await self.browsers[browser_id].close()
                del self.browsers[browser_id]
                logger.info(f"Closed browser instance: {browser_id}")
    
    async def close_all(self) -> None:
        """Close all browser instances"""
        async with self.lock:
            for browser_id, browser in list(self.browsers.items()):
                await browser.close()
                del self.browsers[browser_id]
            logger.info("Closed all browser instances")


# Global manager instance
_manager = BrowserAutomationManager()


async def get_browser_manager() -> BrowserAutomationManager:
    """Get global browser automation manager"""
    return _manager


# Example usage and integration with SunaBridge
async def handle_browser_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle browser automation command from SunaBridge
    
    Args:
        command: Command dict with action and parameters
        
    Returns:
        Result of command execution
        
    Example command formats:
    {
        "action": "navigate",
        "url": "https://google.com",
        "browser_id": "session-123"
    }
    {
        "action": "click",
        "selector": "button.search",
        "browser_id": "session-123"
    }
    {
        "action": "take_screenshot",
        "browser_id": "session-123"
    }
    """
    try:
        action = command.get("action")
        browser_id = command.get("browser_id", "default")
        
        manager = await get_browser_manager()
        browser = await manager.get_browser(browser_id)
        
        if not browser:
            # Auto-create if doesn't exist
            browser = await manager.create_browser(browser_id)
        
        # Route to appropriate action
        if action == "navigate":
            return await browser.navigate(command.get("url", ""))
        
        elif action == "screenshot":
            return await browser.take_screenshot(command.get("filename"))
        
        elif action == "click":
            return await browser.click(command.get("selector", ""))
        
        elif action == "type":
            return await browser.type_text(
                command.get("selector", ""),
                command.get("text", "")
            )
        
        elif action == "execute_js":
            return await browser.execute_javascript(command.get("script", ""))
        
        elif action == "press_key":
            return await browser.press_key(command.get("key", ""))
        
        elif action == "wait_for_selector":
            return await browser.wait_for_selector(command.get("selector", ""))
        
        elif action == "get_content":
            return await browser.get_page_content()
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }
    
    except Exception as e:
        logger.error(f"Command handler error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
