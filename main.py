import asyncio
import os
import pydantic
import psycopg2
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import schedule
import time
from typing import List, Optional

from browserbase import Browserbase
from browser_use import Agent
from browser_use.browser.session import BrowserSession
from browser_use.browser import BrowserProfile
from browser_use.llm import ChatOpenAI

# Load environment variables
load_dotenv()

class ScheduledTask(pydantic.BaseModel):
    id: str
    user_id: str
    task_name: str
    query: str
    data_structure: Optional[str]
    schedule: str
    last_run_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
    
    def get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def get_tasks_due_for_execution(self) -> List[ScheduledTask]:
        """Get all active tasks that are due for execution based on their schedule"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Get all active tasks
                cursor.execute("""
                    SELECT id, user_id, task_name, query, data_structure, schedule, 
                           last_run_at, is_active, created_at, updated_at
                    FROM scheduled_tasks 
                    WHERE is_active = true
                """)
                
                tasks = []
                for row in cursor.fetchall():
                    task = ScheduledTask(
                        id=row[0],
                        user_id=row[1],
                        task_name=row[2],
                        query=row[3],
                        data_structure=row[4],
                        schedule=row[5],
                        last_run_at=row[6],
                        is_active=row[7],
                        created_at=row[8],
                        updated_at=row[9]
                    )
                    
                    # Check if task is due for execution
                    if self._is_task_due(task):
                        tasks.append(task)
                
                return tasks
        finally:
            conn.close()
    
    def _is_task_due(self, task: ScheduledTask) -> bool:
        """Check if a task is due for execution based on its schedule"""
        now = datetime.utcnow()
        
        # If never run before, it's due
        if task.last_run_at is None:
            return True
        
        # Parse schedule (assuming format like "every 1 hour", "every 30 minutes", etc.)
        schedule_text = task.schedule.lower()
        
        if "every" in schedule_text:
            if "hour" in schedule_text:
                # Extract number of hours
                try:
                    hours = int(''.join(filter(str.isdigit, schedule_text)))
                    next_run = task.last_run_at + timedelta(hours=hours)
                    return now >= next_run
                except ValueError:
                    # Default to 1 hour if parsing fails
                    next_run = task.last_run_at + timedelta(hours=1)
                    return now >= next_run
            
            elif "minute" in schedule_text:
                # Extract number of minutes
                try:
                    minutes = int(''.join(filter(str.isdigit, schedule_text)))
                    next_run = task.last_run_at + timedelta(minutes=minutes)
                    return now >= next_run
                except ValueError:
                    # Default to 30 minutes if parsing fails
                    next_run = task.last_run_at + timedelta(minutes=30)
                    return now >= next_run
            
            elif "day" in schedule_text:
                # Extract number of days
                try:
                    days = int(''.join(filter(str.isdigit, schedule_text)))
                    next_run = task.last_run_at + timedelta(days=days)
                    return now >= next_run
                except ValueError:
                    # Default to 1 day if parsing fails
                    next_run = task.last_run_at + timedelta(days=1)
                    return now >= next_run
        
        # Default: run every hour if schedule is unclear
        next_run = task.last_run_at + timedelta(hours=1)
        return now >= next_run
    
    def update_last_run_time(self, task_id: str):
        """Update the last_run_at timestamp for a task"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE scheduled_tasks 
                    SET last_run_at = NOW() 
                    WHERE id = %s
                """, (task_id,))
                conn.commit()
        finally:
            conn.close()

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

async def execute_scheduled_task(task: ScheduledTask, db_manager: DatabaseManager):
    """Execute a single scheduled task"""
    print(f"🔄 Executing task: {task.task_name} (ID: {task.id})")
    print(f"📝 Task query: {task.query}")
    
    try:
        # Create browser session
        session = await create_browserbase_session()
        browser_profile = create_browser_profile()
        
        async with ManagedBrowserSession(session.connect_url, browser_profile) as browser_session:
            # Execute the task
            result = await run_automation_task(browser_session, task.query)
            print(f"✅ Task '{task.task_name}' completed successfully")
            print(f"📊 Result: {result}")
            
            # Update last run time in database
            db_manager.update_last_run_time(task.id)
            print(f"📅 Updated last_run_at for task {task.id}")
            
    except Exception as e:
        print(f"❌ Failed to execute task '{task.task_name}': {e}")
        # Still update last run time to prevent infinite retries
        db_manager.update_last_run_time(task.id)
        print(f"📅 Updated last_run_at for task {task.id} despite failure")

async def check_and_execute_tasks():
    """Main function to check for due tasks and execute them"""
    print(f"🕐 Checking for scheduled tasks at {datetime.utcnow()}")
    
    # Initialize database manager
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return
    
    db_manager = DatabaseManager(database_url)
    
    try:
        # Get tasks that are due for execution
        due_tasks = db_manager.get_tasks_due_for_execution()
        
        if not due_tasks:
            print("ℹ️  No tasks due for execution")
            return
        
        print(f"📋 Found {len(due_tasks)} task(s) due for execution")
        
        # Execute each due task
        for task in due_tasks:
            await execute_scheduled_task(task, db_manager)
            
    except Exception as e:
        print(f"❌ Error checking/executing tasks: {e}")

def main():
    """Main entry point for the script"""
    print("🚀 Starting Cron Fetch Browser Task Runner")
    print(f"⏰ Started at: {datetime.utcnow()}")
    
    # Check if required environment variables are set
    required_env_vars = ["DATABASE_URL", "BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return
    
    # Run the task checker once
    asyncio.run(check_and_execute_tasks())
    
    print(f"✅ Task runner completed at: {datetime.utcnow()}")

if __name__ == "__main__":
    main()