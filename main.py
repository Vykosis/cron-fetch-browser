import asyncio
import os
import pydantic
import psycopg2
from datetime import datetime, timedelta, timezone
import json
from dotenv import load_dotenv
import schedule
import time
from typing import List, Optional
import aiohttp
import asyncio

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
        now = datetime.now(timezone.utc)
        
        # If never run before, it's due
        if task.last_run_at is None:
            return True
        
        # Ensure last_run_at is timezone-aware
        last_run = task.last_run_at
        if last_run.tzinfo is None:
            # If naive, assume UTC
            last_run = last_run.replace(tzinfo=timezone.utc)
        
        # Parse schedule (assuming format like "every 1 hour", "every 30 minutes", etc.)
        schedule_text = task.schedule.lower()
        
        if "every" in schedule_text:
            if "hour" in schedule_text:
                # Extract number of hours
                try:
                    hours = int(''.join(filter(str.isdigit, schedule_text)))
                    next_run = last_run + timedelta(hours=hours)
                    return now >= next_run
                except ValueError:
                    # Default to 1 hour if parsing fails
                    next_run = last_run + timedelta(hours=1)
                    return now >= next_run
            
            elif "minute" in schedule_text:
                # Extract number of minutes
                try:
                    minutes = int(''.join(filter(str.isdigit, schedule_text)))
                    next_run = last_run + timedelta(minutes=minutes)
                    return now >= next_run
                except ValueError:
                    # Default to 30 minutes if parsing fails
                    next_run = last_run + timedelta(minutes=30)
                    return now >= next_run
            
            elif "day" in schedule_text:
                # Extract number of days
                try:
                    days = int(''.join(filter(str.isdigit, schedule_text)))
                    next_run = last_run + timedelta(days=days)
                    return now >= next_run
                except ValueError:
                    # Default to 1 day if parsing fails
                    next_run = last_run + timedelta(days=1)
                    return now >= next_run
        
        # Default: run every hour if schedule is unclear
        next_run = last_run + timedelta(hours=1)
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

class BrowserUseAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.browser-use.com/api/v1"
    
    async def run_task(self, task: str, data_structure: Optional[str] = None, allowed_domains: Optional[List[str]] = None) -> str:
        """Run a task using Browser-Use Cloud API"""
        async with aiohttp.ClientSession() as session:
            # Prepare the request payload
            payload = {
                "task": task,
                "llm_model": "gpt-4.1-mini"
            }
            
            # Add structured output if provided
            if data_structure:
                payload["structured_output_json"] = data_structure
            
            # Add allowed domains if provided
            if allowed_domains:
                payload["allowed_domains"] = allowed_domains
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            print(f"🚀 Starting Browser-Use task: {task[:100]}...")
            
            # Start the task
            async with session.post(
                f"{self.base_url}/run-task",
                headers=headers,
                json=payload
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise Exception(f"Failed to start task: {response.status} - {error_text}")
                
                result = await response.json()
                task_id = result.get("id")
                
                if not task_id:
                    detail = result.get("detail", "Unknown error")
                    raise Exception(f"Failed to get task ID: {detail}")
                
                print(f"📋 Task started with ID: {task_id}")
                print(f"🔗 Task URL: https://api.browser-use.com/api/v1/task/{task_id}")
                
                # Give the task a moment to initialize
                print("⏳ Waiting 3 seconds for task to initialize...")
                await asyncio.sleep(3)
                
                # Poll for task completion and wait for it to finish
                print(f"🔄 Beginning to poll task {task_id} for completion...")
                final_result = await self._poll_task_completion(session, task_id, headers)
                print(f"🎉 Task {task_id} completed with result: {final_result[:200]}...")
                return final_result
    
    async def _poll_task_completion(self, session: aiohttp.ClientSession, task_id: str, headers: dict) -> str:
        """Poll for task completion and return results"""
        max_attempts = 120  # 10 minutes with 5-second intervals
        attempt = 0
        
        print(f"🔄 Starting to poll task {task_id} for completion...")
        
        while attempt < max_attempts:
            try:
                print(f"📡 Polling attempt {attempt + 1}/{max_attempts} for task {task_id}...")
                
                async with session.get(
                    f"{self.base_url}/task/{task_id}",
                    headers=headers
                ) as response:
                    if not response.ok:
                        error_text = await response.text()
                        print(f"⚠️  Error checking task status: {response.status} - {error_text}")
                        await asyncio.sleep(5)
                        attempt += 1
                        continue
                    
                    task_data = await response.json()
                    status = task_data.get("status")
                    output = task_data.get("output", "")
                    
                    print(f"📊 Task {task_id} status: {status} (attempt {attempt + 1}/{max_attempts})")
                    
                    # Check for completion statuses
                    if status == "finished":
                        result = output if output else "Task completed successfully"
                        print(f"✅ Task {task_id} finished successfully")
                        print(f"📄 Task output: {result[:500]}...")
                        return str(result)
                    
                    elif status == "failed":
                        error = task_data.get("error", "Unknown error")
                        print(f"❌ Task {task_id} failed: {error}")
                        raise Exception(f"Task failed: {error}")
                    
                    elif status == "stopped":
                        result = output if output else "Task was stopped"
                        print(f"⏹️  Task {task_id} was stopped")
                        print(f"📄 Task output: {result[:500]}...")
                        return str(result)
                    
                    elif status in ["running", "pending", "queued"]:
                        # Task is still running, wait and check again
                        print(f"⏳ Task {task_id} is {status}, waiting 5 seconds...")
                        await asyncio.sleep(5)
                        attempt += 1
                        continue
                    
                    else:
                        print(f"⚠️  Unknown status '{status}' for task {task_id}")
                        print(f"📄 Full response: {task_data}")
                        await asyncio.sleep(5)
                        attempt += 1
                        continue
                        
            except Exception as e:
                print(f"⚠️  Error polling task status: {e}")
                await asyncio.sleep(5)
                attempt += 1
        
        print(f"⏰ Task {task_id} timed out after {max_attempts * 5} seconds (10 minutes)")
        raise Exception(f"Task {task_id} timed out after {max_attempts * 5} seconds (10 minutes)")

async def execute_scheduled_task(task: ScheduledTask, db_manager: DatabaseManager):
    """Execute a single scheduled task using Browser-Use Cloud API"""
    print(f"🔄 Executing task: {task.task_name} (ID: {task.id})")
    print(f"📝 Task query: {task.query}")
    
    try:
        # Initialize Browser-Use API
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            raise Exception("BROWSER_USE_API_KEY environment variable not set")
        
        browser_use = BrowserUseAPI(api_key)
        
        # Execute the task
        result = await browser_use.run_task(
            task=task.query,
            data_structure=task.data_structure
        )
        
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
    print(f"🕐 Checking for scheduled tasks at {datetime.now(timezone.utc)}")
    
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
    print(f"⏰ Started at: {datetime.now(timezone.utc)}")
    
    # Check if required environment variables are set
    required_env_vars = ["DATABASE_URL", "BROWSER_USE_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return
    
    # Run the task checker once
    asyncio.run(check_and_execute_tasks())
    
    print(f"✅ Task runner completed at: {datetime.now(timezone.utc)}")

if __name__ == "__main__":
    main()