import asyncio
import os
import pydantic
from dotenv import load_dotenv

from browserbase import Browserbase
from browser_use import Agent
from browser_use.browser.session import BrowserSession
from browser_use.browser import BrowserProfile
from browser_use.llm import ChatOpenAI

from fastapi import FastAPI

app = FastAPI()

class ManagedBrowserSession:
    """Context manager for proper BrowserSession lifecycle management"""
    
    def __init__(self, cdp_url: str, browser_profile: BrowserProfile):
        self.cdp_url = cdp_url
        self.browser_profile = browser_profile
        self.browser_session = None
        
    async def __aenter__(self) -> BrowserSession:
        try:
            self.browser_session = BrowserSession(
                cdp_url=self.cdp_url,
                browser_profile=self.browser_profile,
                keep_alive=False,  # Essential for proper cleanup
                initialized=False,
            )
            
            await self.browser_session.start()
            print("✅ Browser session initialized successfully")
            return self.browser_session
            
        except Exception as e:
            print(f"❌ Failed to initialize browser session: {e}")
            await self._emergency_cleanup()
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session_properly()
    
    async def _close_session_properly(self):
        playwright_instance = None
        
        try:
            if self.browser_session:
                # Get playwright instance before closing session
                if hasattr(self.browser_session, 'playwright'):
                    playwright_instance = self.browser_session.playwright
                
                # Close browser session first
                if self.browser_session.initialized:
                    await self.browser_session.stop()
                    print("✅ Browser session closed successfully")
                    
        except Exception as e:
            error_msg = str(e).lower()
            if "browser is closed" in error_msg or "disconnected" in error_msg:
                print("ℹ️  Browser session was already closed (expected behavior)")
            else:
                print(f"⚠️  Error during browser session closure: {e}")
        
        finally:
            # Stop playwright instance - critical for preventing hanging processes
            if playwright_instance:
                try:
                    await playwright_instance.stop()
                    print("✅ Playwright instance stopped successfully")
                except Exception as e:
                    print(f"⚠️  Error stopping Playwright: {e}")
            
            await self._final_cleanup()
    
    async def _emergency_cleanup(self):
        try:
            if self.browser_session:
                if hasattr(self.browser_session, 'playwright'):
                    await self.browser_session.playwright.stop()
                if self.browser_session.initialized:
                    await self.browser_session.stop()
        except Exception as e:
            print(f"⚠️  Emergency cleanup error: {e}")
        finally:
            await self._final_cleanup()
    
    async def _final_cleanup(self):
        self.browser_session = None


async def create_browserbase_session():
    load_dotenv()
    
    bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])
    session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])
    
    print(f"Session ID: {session.id}")
    print(f"Debug URL: https://www.browserbase.com/sessions/{session.id}")
    
    return session


def create_browser_profile() -> BrowserProfile:
    return BrowserProfile(
        keep_alive=False,  # Essential for proper cleanup
        wait_between_actions=2.0,
        default_timeout=60000,
        default_navigation_timeout=60000,
        headless=False,
        
    )


async def run_automation_task(browser_session: BrowserSession, task: str) -> str:
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.0)

    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser_session,
        max_failures=5,
        retry_delay=5,
        max_actions_per_step=3,
        extend_system_message = """ REMEMBER the most important RULE: Stay on the same tab, never open a new tab!!! """
    )
    
    try:
        print("🚀 Starting agent task...")
        result = await agent.run(max_steps=20)
        print("🎉 Task completed successfully!")
        return str(result)
        
    except Exception as e:
        # Handle expected browser disconnection after successful completion
        error_msg = str(e).lower()
        if "browser is closed" in error_msg or "disconnected" in error_msg:
            print("✅ Task completed - Browser session ended normally")
            return "Task completed successfully (session ended normally)"
        else:
            print(f"❌ Agent execution error: {e}")
            raise
            
    finally:
        del agent


class Task(pydantic.BaseModel):
    task: str

@app.post("/run-task")
async def run_task(task: Task):
    print(f"Running task: {task.task}")
    session = await create_browserbase_session()
    browser_profile = create_browser_profile()
    
    async with ManagedBrowserSession(session.connect_url, browser_profile) as browser_session:
        result = await run_automation_task(browser_session, task.task)
        return {"result": result}